"""Regression tests for the real-key OCR failure (500 Internal Server Error).

Root cause: GOOGLE_VISION_API_KEY in backend/.env started with an invisible
U+200F RIGHT-TO-LEFT MARK. httpx cannot put non-ASCII text in an HTTP header,
raised UnicodeEncodeError (not an httpx.HTTPError), and the generic handler
returned 500 without logging anything. These tests pin the fixed behaviour:
actionable, secret-free diagnostics and no opaque 500s.
"""

from __future__ import annotations

import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.domain.errors import OcrNotConfiguredError, OcrProviderError
from app.main import create_app
from app.ocr.credentials import describe_key_problem
from app.ocr.factory import build_ocr_provider
from app.ocr.google_vision import GoogleVisionOcrProvider
from tests.test_ocr import image_bytes, ocr_image

KEY = "AIza" + "x" * 35  # synthetic, correctly shaped
RLM_KEY = "‏" + KEY


@pytest.fixture
def logs(caplog):
    lg = logging.getLogger("mizan")
    old = lg.propagate
    lg.propagate = True
    caplog.set_level(logging.INFO, logger="mizan")
    yield caplog
    lg.propagate = old


def app_with(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def post_png(c: TestClient):
    return c.post("/api/v1/ocr", files={"image": ("p.png", image_bytes(), "image/png")})


# --- credential format ------------------------------------------------------


def test_valid_key_has_no_problem():
    assert describe_key_problem(KEY) is None


@pytest.mark.parametrize(
    "bad,expected",
    [
        (RLM_KEY, "U+200F RIGHT-TO-LEFT MARK at position 0"),
        (KEY + "‎", "U+200E LEFT-TO-RIGHT MARK at position 39"),
        ("﻿" + KEY, "U+FEFF ZERO WIDTH NO-BREAK SPACE"),
        (KEY + " ", "U+0020 SPACE at position 39"),
        ('"' + KEY + '"', "wrapped in quotes"),
    ],
)
def test_key_problems_are_named_without_revealing_the_key(bad, expected):
    msg = describe_key_problem(bad)
    assert msg and expected in msg
    assert KEY not in msg and "AIza" not in msg


def test_factory_refuses_malformed_key():
    p = build_ocr_provider(Settings(ocr_provider="google_vision", google_vision_api_key=RLM_KEY))
    assert isinstance(p, GoogleVisionOcrProvider)
    assert p.is_configured() is False
    assert "U+200F" in (p.config_problem or "")


async def test_malformed_key_raises_not_configured_before_any_request():
    calls = []
    p = GoogleVisionOcrProvider(
        api_key=None,
        config_problem=describe_key_problem(RLM_KEY),
        transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(200)),
    )
    with pytest.raises(OcrNotConfiguredError):
        await p.extract_text(ocr_image())
    assert calls == []


def test_api_reports_malformed_key_clearly_instead_of_500(logs):
    s = Settings(ocr_provider="google_vision", google_vision_api_key=RLM_KEY)
    c = app_with(s)
    r = post_png(c)
    assert r.status_code == 503
    body = r.json()
    assert body["error"]["code"] == "ocr_not_configured"
    assert "U+200F RIGHT-TO-LEFT MARK at position 0" in body["error"]["message"]
    health = c.get("/api/v1/health").json()["ocr"]
    assert health["status"] == "invalid_credentials" and "U+200F" in health["detail"]
    for text in (r.text, c.get("/api/v1/health").text, logs.text):
        assert KEY not in text
    assert "U+200F" in logs.text


def test_startup_warns_about_malformed_key(logs, monkeypatch):
    monkeypatch.setenv("OCR_PROVIDER", "google_vision")
    monkeypatch.setenv("GOOGLE_VISION_API_KEY", RLM_KEY)
    get_settings.cache_clear()
    create_app()
    assert "not usable" in logs.text and "U+200F" in logs.text
    assert KEY not in logs.text


# --- request build errors never become opaque 500s ---------------------------


async def test_request_build_error_is_a_provider_error(logs):
    # Bypass config validation to prove the adapter itself is defensive.
    p = GoogleVisionOcrProvider(
        api_key=RLM_KEY, transport=httpx.MockTransport(lambda r: httpx.Response(200))
    )
    with pytest.raises(OcrProviderError) as e:
        await p.extract_text(ocr_image())
    assert "UnicodeEncodeError" in str(e.value)
    assert KEY not in logs.text


# --- upstream Google errors are logged with status/reason (no key) -----------

GOOGLE_403 = {
    "error": {
        "code": 403,
        "message": "Cloud Vision API has not been used in project 123 before or it is disabled.",
        "status": "PERMISSION_DENIED",
        "details": [
            {
                "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                "reason": "SERVICE_DISABLED",
                "domain": "googleapis.com",
            }
        ],
    }
}


def svc_with(transport):
    from app.ocr.service import OcrService

    return OcrService(
        GoogleVisionOcrProvider(api_key=KEY, transport=transport), low_confidence_threshold=0.6
    )


def test_google_rejection_is_actionable_in_logs_and_safe_in_response(logs):
    from app.api.v1.ocr import get_ocr_service

    s = Settings(ocr_provider="google_vision", google_vision_api_key=KEY)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: s
    app.dependency_overrides[get_ocr_service] = lambda: svc_with(
        httpx.MockTransport(lambda r: httpx.Response(403, json=GOOGLE_403))
    )
    r = TestClient(app).post("/api/v1/ocr", files={"image": ("p.png", image_bytes(), "image/png")})
    assert r.status_code == 502
    err = r.json()["error"]
    assert err["code"] == "ocr_error" and err["retryable"] is False
    assert "HTTP 403 PERMISSION_DENIED (SERVICE_DISABLED)" in err["message"]
    assert "project 123" not in r.text  # full Google message only in dev logs
    assert "http=403 status=PERMISSION_DENIED reason=SERVICE_DISABLED" in logs.text
    assert "has not been used in project 123" in logs.text
    assert KEY not in logs.text and KEY not in r.text


@pytest.mark.parametrize("code,retryable", [(429, True), (500, True), (503, True), (400, False)])
async def test_retryability_follows_http_status(code, retryable):
    p = GoogleVisionOcrProvider(
        api_key=KEY, transport=httpx.MockTransport(lambda r: httpx.Response(code, content=b"oops"))
    )
    with pytest.raises(OcrProviderError) as e:
        await p.extract_text(ocr_image())
    assert e.value.retryable is retryable


async def test_unexpected_response_shape_is_a_provider_error(logs):
    weird = {
        "responses": [
            {
                "fullTextAnnotation": {
                    "text": "نص",
                    "pages": [
                        {
                            "blocks": [
                                {
                                    "paragraphs": [
                                        {"words": [{"confidence": 1.7, "symbols": [{"text": "ن"}]}]}
                                    ]
                                }
                            ]
                        }
                    ],
                }
            }
        ]
    }
    p = GoogleVisionOcrProvider(
        api_key=KEY, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=weird))
    )
    with pytest.raises(OcrProviderError):
        await p.extract_text(ocr_image())
    assert "expected shape" in logs.text
    assert "نص" not in logs.text  # OCR text is never logged


def test_unexpected_exception_is_logged_with_traceback_and_redacted(logs):
    from app.api.v1.ocr import get_ocr_service
    from app.ocr.base import OcrProvider

    class Boom(OcrProvider):
        name = "boom"

        def is_configured(self):
            return True

        async def extract_text(self, image):
            raise RuntimeError(f"bad thing with {KEY}")

    from app.ocr.service import OcrService

    s = Settings(ocr_provider="google_vision", google_vision_api_key=KEY)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: s
    app.dependency_overrides[get_ocr_service] = lambda: OcrService(
        Boom(), low_confidence_threshold=0.6
    )
    r = TestClient(app).post("/api/v1/ocr", files={"image": ("p.png", image_bytes(), "image/png")})
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error"
    assert "Traceback" in logs.text and "RuntimeError" in logs.text
    assert "[REDACTED]" in logs.text and KEY not in logs.text and KEY not in r.text
