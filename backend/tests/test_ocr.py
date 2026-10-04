"""Task 3 — OCR: structure, validation, provider adapter, API, separation rules."""

from __future__ import annotations

import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from app.api.v1.ocr import get_ocr_service
from app.config import Settings, get_settings
from app.domain.enums import SystemErrorCode, VerificationStatus
from app.domain.errors import OcrProviderError, OcrTimeoutError
from app.domain.inputs import ExtractionInput
from app.domain.ocr import (
    MAX_UPLOAD_BYTES,
    OcrExtraction,
    OcrImageInfo,
    OcrInputErrorCode,
    OcrStatus,
    OcrWarningCode,
    ReviewedOcrText,
)
from app.main import create_app
from app.ocr.base import OcrImage, OcrProvider, ProviderOcrResult, ProviderWord
from app.ocr.google_vision import ENDPOINT, GoogleVisionOcrProvider, parse_annotation
from app.ocr.image_validation import OcrInputError, validate_image
from app.ocr.service import OcrService

ARABIC = "قراءة سورة الكهف يوم الجمعة\nسبب في حصول نور بين الجمعتين."


def image_bytes(fmt: str = "PNG", size: tuple[int, int] = (800, 600)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (255, 255, 255)).save(buf, format=fmt)
    return buf.getvalue()


class FakeProvider(OcrProvider):
    name = "fake"

    def __init__(self, result: ProviderOcrResult | None = None, exc: Exception | None = None):
        self.result, self.exc, self.calls = result, exc, 0

    def is_configured(self) -> bool:
        return True

    async def extract_text(self, image: OcrImage) -> ProviderOcrResult:
        self.calls += 1
        if self.exc:
            raise self.exc
        assert self.result is not None
        return self.result


def ocr_image(size=(800, 600)) -> OcrImage:
    return validate_image(image_bytes(size=size))


# --- Image content validation ------------------------------------------------


@pytest.mark.parametrize("fmt,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg")])
def test_valid_images(fmt, mime):
    img = validate_image(image_bytes(fmt))
    assert img.mime_type == mime and (img.width, img.height) == (800, 600)


@pytest.mark.parametrize(
    "data,code",
    [
        (b"", OcrInputErrorCode.EMPTY_FILE),
        (b"hello, this is a text file renamed to .png", OcrInputErrorCode.UNSUPPORTED_TYPE),
        (b"GIF89a" + b"\x00" * 20, OcrInputErrorCode.UNSUPPORTED_TYPE),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 40, OcrInputErrorCode.UNREADABLE_IMAGE),  # fake header
        (b"\xff\xd8\xff" + b"\x00" * 40, OcrInputErrorCode.UNREADABLE_IMAGE),
    ],
)
def test_invalid_images(data, code):
    with pytest.raises(OcrInputError) as e:
        validate_image(data)
    assert e.value.code == code


def test_size_limit_is_7_mib():
    assert MAX_UPLOAD_BYTES == 7 * 1024 * 1024
    with pytest.raises(OcrInputError) as e:
        validate_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * MAX_UPLOAD_BYTES)
    assert e.value.code == OcrInputErrorCode.FILE_TOO_LARGE


# --- Service: status / warnings / raw text -----------------------------------


async def test_successful_ocr_keeps_raw_text_exactly():
    raw = f"  {ARABIC}\n"
    svc = OcrService(
        FakeProvider(
            ProviderOcrResult(
                text=raw,
                words=[ProviderWord(text="سورة", confidence=0.98)],
                page_confidences=[0.97],
                detected_languages=["ar"],
            )
        ),
        low_confidence_threshold=0.6,
    )
    out = await svc.extract(ocr_image())
    assert out.status == OcrStatus.COMPLETED and out.warnings == []
    assert out.raw_text == raw
    assert out.confidence and out.confidence.page_confidence == pytest.approx(0.97)
    assert out.detected_languages == ["ar"] and out.provider == "fake"


async def test_partial_ocr_flags_low_confidence_words():
    words = [
        ProviderWord(text="الكهف", confidence=0.95),
        ProviderWord(text="الجمعتين", confidence=0.31),
    ]
    svc = OcrService(
        FakeProvider(ProviderOcrResult(text=ARABIC, words=words)), low_confidence_threshold=0.6
    )
    out = await svc.extract(ocr_image())
    assert out.status == OcrStatus.COMPLETED_WITH_WARNINGS
    assert [w.code for w in out.warnings] == [OcrWarningCode.LOW_CONFIDENCE_TEXT]
    assert out.confidence.low_confidence_word_count == 1
    assert out.confidence.low_confidence_words[0].text == "الجمعتين"
    assert out.raw_text == ARABIC  # nothing removed or "fixed"


async def test_no_confidence_is_never_invented():
    svc = OcrService(FakeProvider(ProviderOcrResult(text=ARABIC)), low_confidence_threshold=0.6)
    out = await svc.extract(ocr_image())
    assert out.confidence is None and out.status == OcrStatus.COMPLETED


async def test_low_resolution_warning_from_documented_minimum():
    svc = OcrService(FakeProvider(ProviderOcrResult(text=ARABIC)), low_confidence_threshold=0.6)
    out = await svc.extract(ocr_image(size=(300, 200)))
    assert out.status == OcrStatus.COMPLETED_WITH_WARNINGS
    assert out.warnings[0].code == OcrWarningCode.LOW_RESOLUTION_IMAGE


@pytest.mark.parametrize("text", ["", "   \n  "])
async def test_empty_ocr_result(text):
    svc = OcrService(FakeProvider(ProviderOcrResult(text=text)), low_confidence_threshold=0.6)
    out = await svc.extract(ocr_image())
    assert out.status == OcrStatus.NO_TEXT_FOUND
    assert out.raw_text == text


def test_extraction_status_consistency_enforced():
    info = OcrImageInfo(mime_type="image/png", size_bytes=1, width=1, height=1)
    with pytest.raises(ValidationError):
        OcrExtraction(provider="x", status=OcrStatus.COMPLETED, raw_text="", image=info)
    with pytest.raises(ValidationError):
        OcrExtraction(
            provider="x", status=OcrStatus.COMPLETED_WITH_WARNINGS, raw_text="a", image=info
        )


# --- Raw vs reviewed separation ------------------------------------------------


def test_reviewed_text_is_separate_from_raw():
    r = ReviewedOcrText(ocr_id="o", provider="fake", raw_text="نص خام", reviewed_text="نص مُراجَع")
    assert r.raw_text == "نص خام" and r.reviewed_text == "نص مُراجَع" and r.edited_by_user
    with pytest.raises(ValidationError):
        ReviewedOcrText(ocr_id="o", provider="fake", raw_text="x", reviewed_text="  ")


def test_only_reviewed_ocr_text_may_enter_extraction():
    with pytest.raises(ValidationError):
        ExtractionInput(mode="full_content", input_type="image", text="raw ocr")
    ok = ExtractionInput(
        mode="full_content", input_type="image", text="reviewed", ocr_text_reviewed_by_user=True
    )
    assert ok.text == "reviewed"


def test_ocr_errors_are_not_verification_statuses():
    statuses = {s.value for s in VerificationStatus}
    for code in (
        SystemErrorCode.OCR_ERROR,
        SystemErrorCode.OCR_TIMEOUT,
        SystemErrorCode.OCR_NOT_CONFIGURED,
    ):
        assert code.value not in statuses


# --- Google Vision adapter (mocked HTTP; no real network) --------------------

VISION_RESPONSE = {
    "responses": [
        {
            "fullTextAnnotation": {
                "text": ARABIC,
                "pages": [
                    {
                        "confidence": 0.9,
                        "property": {
                            "detectedLanguages": [{"languageCode": "ar", "confidence": 1}]
                        },
                        "blocks": [
                            {
                                "paragraphs": [
                                    {
                                        "words": [
                                            {
                                                "confidence": 0.99,
                                                "symbols": [{"text": "ق"}, {"text": "ر"}],
                                            },
                                            {
                                                "confidence": 0.4,
                                                "symbols": [
                                                    {"text": "ن"},
                                                    {"text": "و"},
                                                    {"text": "ر"},
                                                ],
                                            },
                                        ]
                                    }
                                ]
                            }
                        ],
                    }
                ],
            }
        }
    ]
}


def mock_transport(handler):
    return httpx.MockTransport(handler)


async def test_google_vision_request_and_parse():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"], seen["headers"], seen["body"] = (
            str(req.url),
            req.headers,
            json.loads(req.content),
        )
        return httpx.Response(200, json=VISION_RESPONSE)

    p = GoogleVisionOcrProvider(api_key="test-key", transport=mock_transport(handler))
    res = await p.extract_text(ocr_image())
    assert seen["url"] == ENDPOINT  # key is NOT in the URL
    assert seen["headers"]["x-goog-api-key"] == "test-key"
    req = seen["body"]["requests"][0]
    assert req["features"] == [{"type": "DOCUMENT_TEXT_DETECTION"}]
    assert "imageContext" not in req  # auto-detect by default
    assert res.text == ARABIC
    assert [(w.text, w.confidence) for w in res.words] == [("قر", 0.99), ("نور", 0.4)]
    assert res.page_confidences == [0.9] and res.detected_languages == ["ar"]


async def test_google_vision_language_hints_optional():
    def handler(req):
        assert json.loads(req.content)["requests"][0]["imageContext"] == {"languageHints": ["ar"]}
        return httpx.Response(200, json={"responses": [{}]})

    p = GoogleVisionOcrProvider(
        api_key="k", language_hints=["ar"], transport=mock_transport(handler)
    )
    assert (await p.extract_text(ocr_image())).text == ""


def test_parse_without_text_annotation():
    assert parse_annotation({}).text == ""


@pytest.mark.parametrize(
    "response,exc",
    [
        (httpx.Response(403, json={"error": {"code": 403}}), OcrProviderError),
        (
            httpx.Response(200, json={"responses": [{"error": {"code": 3, "message": "bad"}}]}),
            OcrProviderError,
        ),
        (httpx.Response(200, content=b"not json"), OcrProviderError),
    ],
)
async def test_google_vision_errors_are_technical(response, exc):
    p = GoogleVisionOcrProvider(api_key="k", transport=mock_transport(lambda r: response))
    with pytest.raises(exc):
        await p.extract_text(ocr_image())


async def test_google_vision_timeout():
    def handler(req):
        raise httpx.ReadTimeout("slow", request=req)

    p = GoogleVisionOcrProvider(api_key="k", transport=mock_transport(handler))
    with pytest.raises(OcrTimeoutError):
        await p.extract_text(ocr_image())


def test_google_vision_unconfigured():
    assert GoogleVisionOcrProvider(api_key=None).is_configured() is False


# --- API -----------------------------------------------------------------------


def client(service: OcrService | None, settings: Settings | None = None) -> TestClient:
    app = create_app()
    s = settings or Settings(ocr_provider="google_vision", google_vision_api_key="sk-secret-test")
    app.dependency_overrides[get_settings] = lambda: s
    app.dependency_overrides[get_ocr_service] = lambda: service
    return TestClient(app)


def post(c: TestClient, data: bytes, name="page.png", ctype="image/png"):
    return c.post("/api/v1/ocr", files={"image": (name, data, ctype)})


def svc(result=None, exc=None):
    return OcrService(FakeProvider(result, exc), low_confidence_threshold=0.6)


def test_api_success_returns_raw_text_for_review():
    r = post(client(svc(ProviderOcrResult(text=ARABIC))), image_bytes())
    assert r.status_code == 200
    body = r.json()
    assert (
        body["kind"] == "extraction"
        and body["raw_text"] == ARABIC
        and body["status"] == "completed"
    )
    # OCR never produces claims, statuses or evidence
    for forbidden in ("claims", "status_verification", "evidence", "verification"):
        assert forbidden not in body


def test_api_accepts_jpeg():
    r = post(
        client(svc(ProviderOcrResult(text=ARABIC))), image_bytes("JPEG"), "a.jpg", "image/jpeg"
    )
    assert r.status_code == 200 and r.json()["image"]["mime_type"] == "image/jpeg"


def test_api_rejects_renamed_file_by_content():
    service = svc(ProviderOcrResult(text="x"))
    r = post(client(service), b"plain text pretending to be png", "fake.png", "image/png")
    assert r.status_code == 400 and r.json() == {
        "kind": "input_error",
        "code": "unsupported_type",
        "message": "only JPG or PNG images are accepted",
    }
    assert service.provider.calls == 0  # nothing sent to OCR


def test_api_rejects_oversized_file():
    r = post(
        client(svc(ProviderOcrResult(text="x"))), b"\x89PNG\r\n\x1a\n" + b"\0" * MAX_UPLOAD_BYTES
    )
    assert r.status_code == 413 and r.json()["code"] == "file_too_large"


def test_api_empty_result():
    r = post(client(svc(ProviderOcrResult(text=""))), image_bytes())
    assert r.status_code == 200 and r.json()["status"] == "no_text_found"


@pytest.mark.parametrize(
    "exc,status,code",
    [
        (OcrProviderError("boom"), 502, "ocr_error"),
        (OcrTimeoutError("slow"), 504, "ocr_timeout"),
        (RuntimeError("bug"), 500, "internal_error"),
    ],
)
def test_api_technical_failure_is_system_error(exc, status, code):
    r = post(client(svc(exc=exc)), image_bytes())
    assert r.status_code == status
    body = r.json()
    assert body["kind"] == "failure" and body["error"]["code"] == code
    assert body["error"]["code"] not in {s.value for s in VerificationStatus}


def test_api_not_configured():
    s = Settings()  # ocr_provider=none
    r = post(client(None, s), image_bytes())
    assert r.status_code == 503 and r.json()["error"]["code"] == "ocr_not_configured"


def test_api_missing_key_is_not_configured_and_never_leaks():
    s = Settings(ocr_provider="google_vision")
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: s
    r = TestClient(app).post("/api/v1/ocr", files={"image": ("a.png", image_bytes(), "image/png")})
    assert r.status_code == 503


def test_api_limits_and_health_never_expose_key():
    s = Settings(ocr_provider="google_vision", google_vision_api_key="sk-secret-test")
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: s
    c = TestClient(app)
    limits = c.get("/api/v1/ocr/limits")
    assert limits.json() == {
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "accepted_mime_types": ["image/jpeg", "image/png"],
        "provider": "google_vision",
        "configured": True,
    }
    health = c.get("/api/v1/health")
    assert health.json()["ocr"] == {"status": "configured", "detail": "google_vision"}
    for r in (limits, health):
        assert "sk-secret-test" not in r.text
