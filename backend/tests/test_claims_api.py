"""Task 4 API: extraction endpoint, confirmation gate, failure separation, no verification."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.v1.claims import get_llm_provider
from app.config import Settings, get_settings
from app.domain.errors import (
    LLMAuthError,
    LLMContentBlockedError,
    LLMInvalidResponseError,
    LLMNotConfiguredError,
    LLMProviderError,
    LLMRateLimitedError,
    LLMTimeoutError,
)
from app.domain.inputs import MAX_EXTRACTION_INPUT_CHARS
from app.llm.fake import FakeLLMProvider
from app.llm.schemas import ClaimExtractionDraft, ExtractedClaimDraft
from app.main import create_app
from app.pipeline import orchestrator

KAHF = "قراءة سورة الكهف يوم الجمعة واجبة، وهي سبب لمغفرة الذنوب، أنصحكم جميعًا بقراءتها."
SECRET = "SECRET" + "q" * 33


def drafts():
    return ClaimExtractionDraft(
        claims=[
            ExtractedClaimDraft(
                extracted_claim_text="قراءة سورة الكهف يوم الجمعة واجبة.",
                source_excerpt="قراءة سورة الكهف يوم الجمعة واجبة",
                extraction_status="clear",
            ),
            ExtractedClaimDraft(
                extracted_claim_text="قراءة سورة الكهف يوم الجمعة سبب لمغفرة الذنوب.",
                source_excerpt="وهي سبب لمغفرة الذنوب",
                extraction_status="clear",
            ),
        ]
    )


def client(provider, settings=None) -> TestClient:
    app = create_app()
    s = settings or Settings(llm_provider="gemini", gemini_api_key=SECRET)
    app.dependency_overrides[get_settings] = lambda: s
    app.dependency_overrides[get_llm_provider] = lambda: provider
    return TestClient(app)


@pytest.fixture(autouse=True)
def no_verification(monkeypatch):
    """Task 4 must never run the verification pipeline."""

    async def boom(*a, **k):
        raise AssertionError("verification pipeline must not run in Task 4")

    monkeypatch.setattr(orchestrator.VerificationPipeline, "run", boom)


# --- extraction -------------------------------------------------------------------


def test_extract_returns_pending_claims_for_review():
    r = client(FakeLLMProvider([drafts()])).post("/api/v1/claims/extract", json={"text": KAHF})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "extraction"
    assert [c["extracted_claim_text"] for c in body["claims"]] == [
        "قراءة سورة الكهف يوم الجمعة واجبة.",
        "قراءة سورة الكهف يوم الجمعة سبب لمغفرة الذنوب.",
    ]
    assert all(c["user_confirmation_status"] == "pending" for c in body["claims"])
    for c in body["claims"]:
        for forbidden in (
            "status",
            "verdict",
            "grading",
            "evidence",
            "verified_reference",
            "claim_type",
        ):
            assert forbidden not in c


def test_extract_zero_claims_is_success_not_failure():
    r = client(FakeLLMProvider([ClaimExtractionDraft(claims=[])])).post(
        "/api/v1/claims/extract", json={"text": "جزاكم الله خيرًا"}
    )
    assert r.status_code == 200 and r.json()["claims"] == [] and r.json()["kind"] == "extraction"


@pytest.mark.parametrize(
    "text,status,code",
    [("   ", 400, "empty_text"), ("ا" * (MAX_EXTRACTION_INPUT_CHARS + 1), 413, "text_too_long")],
)
def test_extract_input_errors(text, status, code):
    fake = FakeLLMProvider()
    r = client(fake).post("/api/v1/claims/extract", json={"text": text})
    assert r.status_code == status and r.json()["code"] == code and fake.requests == []


def test_extract_without_provider_is_not_configured_failure():
    r = client(None, Settings()).post("/api/v1/claims/extract", json={"text": KAHF})
    assert r.status_code == 503
    body = r.json()
    assert body["kind"] == "failure" and body["error"]["code"] == "llm_not_configured"


class Raising(FakeLLMProvider):
    def __init__(self, exc):
        super().__init__()
        self.exc = exc

    async def generate_structured(self, request, output_type):
        raise self.exc


@pytest.mark.parametrize(
    "exc,status,code,retryable",
    [
        (LLMRateLimitedError(f"quota for {SECRET}"), 429, "llm_rate_limited", True),
        (LLMTimeoutError("slow"), 504, "llm_timeout", True),
        (LLMInvalidResponseError("bad json"), 502, "llm_invalid_response", True),
        (LLMAuthError("HTTP 403 PERMISSION_DENIED"), 503, "llm_auth_failed", False),
        (LLMNotConfiguredError("no key"), 503, "llm_not_configured", False),
        (LLMContentBlockedError("SAFETY"), 422, "llm_content_blocked", False),
        (LLMProviderError("HTTP 500"), 502, "llm_provider_error", True),
        (RuntimeError(f"bug {SECRET}"), 500, "internal_error", True),
    ],
)
def test_provider_failure_is_a_failure_never_no_claims(exc, status, code, retryable):
    r = client(Raising(exc)).post("/api/v1/claims/extract", json={"text": KAHF})
    assert r.status_code == status
    body = r.json()
    assert body["kind"] == "failure" and "claims" not in body
    assert body["error"]["code"] == code and body["error"]["retryable"] is retryable
    assert body["error"]["stage"] == "claim_extraction"
    assert (
        SECRET not in r.text and "PERMISSION_DENIED" not in r.text
    )  # provider internals not exposed


# --- confirmation gate ------------------------------------------------------------


def item(cid, text, origin="extracted", extracted=None, selected=True, **kw):
    return {
        "claim_id": cid,
        "origin": origin,
        "original_text": kw.pop("original_text", text),
        "extracted_claim_text": extracted if origin == "extracted" else None,
        "text": text,
        "selected": selected,
        "extraction_status": "clear" if origin == "extracted" else None,
        **kw,
    }


def confirm(payload):
    return client(FakeLLMProvider()).post("/api/v1/claims/confirm", json=payload)


def test_confirm_uses_edited_text_excludes_deselected_and_includes_manual():
    r = confirm(
        {
            "explicit_user_confirmation": True,
            "claims": [
                item(
                    "a",
                    "قراءة سورة الكهف يوم الجمعة مستحبة.",
                    extracted="قراءة سورة الكهف يوم الجمعة واجبة.",
                ),
                item(
                    "b",
                    "قراءة سورة الكهف سبب لمغفرة الذنوب.",
                    extracted="قراءة سورة الكهف سبب لمغفرة الذنوب.",
                    selected=False,
                ),
                item("c", "صيام عاشوراء يكفر ذنوب سنة.", extracted="صيام عاشوراء يكفر ذنوب سنة."),
                item("m", "الصلاة عماد الدين.", origin="manual"),
            ],
        }
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "confirmed" and body["verification_started"] is False
    assert body["next_stage"] == "claim_classification"
    got = {c["claim_id"]: c for c in body["confirmed_claims"]}
    assert set(got) == {"a", "c", "m"}  # deselected 'b' excluded
    assert (
        got["a"]["confirmed_claim_text"] == "قراءة سورة الكهف يوم الجمعة مستحبة."
    )  # edited text wins
    assert got["a"]["user_confirmation_status"] == "edited"
    assert got["c"]["user_confirmation_status"] == "confirmed"
    assert got["m"]["user_confirmation_status"] == "confirmed"  # manual goes through same gate
    assert all(c["claim_type"] is None for c in got.values())


def test_confirm_zero_selected():
    r = confirm(
        {
            "explicit_user_confirmation": True,
            "claims": [item("a", "x", extracted="x", selected=False)],
        }
    )
    assert r.status_code == 422 and r.json()["code"] == "no_claims_selected"
    r = confirm({"explicit_user_confirmation": True, "claims": []})
    assert r.status_code == 422 and r.json()["code"] == "no_claims_selected"


def test_confirm_requires_explicit_user_confirmation():
    r = confirm({"explicit_user_confirmation": False, "claims": [item("a", "x", extracted="x")]})
    assert r.status_code == 422 and r.json()["code"] == "confirmation_required"
    r = confirm({"claims": [item("a", "x", extracted="x")]})
    assert r.status_code == 422  # field required


def test_confirm_rejects_blank_selected_claim_and_duplicate_ids():
    r = confirm({"explicit_user_confirmation": True, "claims": [item("a", "  ", extracted="x")]})
    assert r.json()["code"] == "empty_claim_text"
    r = confirm(
        {
            "explicit_user_confirmation": True,
            "claims": [item("a", "x", extracted="x"), item("a", "y", extracted="y")],
        }
    )
    assert r.json()["code"] == "duplicate_claim_id"


def test_confirm_rejects_verdict_like_extra_fields():
    bad = item("a", "x", extracted="x")
    bad["status"] = "supported"
    r = confirm({"explicit_user_confirmation": True, "claims": [bad]})
    assert r.status_code == 422


def test_health_reports_llm_without_secret():
    c = client(None, Settings(llm_provider="gemini", gemini_api_key=SECRET))
    llm = c.get("/api/v1/health").json()["llm_provider"]
    assert llm == {"status": "configured", "detail": "gemini (gemini-3.5-flash-lite)"}
    bad = client(None, Settings(llm_provider="gemini", gemini_api_key="‏" + SECRET))
    r = bad.get("/api/v1/health")
    assert r.json()["llm_provider"]["status"] == "invalid_credentials" and SECRET not in r.text


def test_real_gemini_400_surfaces_as_technical_failure_not_no_claims():
    """Regression for the first live smoke test: HTTP 400 INVALID_ARGUMENT from Gemini."""
    import httpx

    from app.llm.gemini import GeminiProvider
    from tests.test_gemini_adapter import REAL_400

    gemini = GeminiProvider(
        api_key=SECRET,
        model="gemini-3.5-flash-lite",
        transport=httpx.MockTransport(lambda r: httpx.Response(400, json=REAL_400)),
    )
    r = client(gemini).post("/api/v1/claims/extract", json={"text": KAHF})
    assert r.status_code == 502
    body = r.json()
    assert body["kind"] == "failure" and "claims" not in body
    assert body["error"]["code"] == "llm_provider_error" and body["error"]["retryable"] is False
    assert "response_format" not in r.text and SECRET not in r.text  # internals not exposed
