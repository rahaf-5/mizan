"""Production pattern: the FIRST Gemini call fails transiently (503 / 429 per-minute), the next
succeeds. Extraction and verification must both complete on the user's first attempt."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.v1.claims import get_llm_provider
from app.api.v1.verify import get_registry
from app.config import Settings, get_settings
from app.llm.gemini import GeminiProvider
from app.llm.schemas import ClaimType, ClassificationSuggestion
from app.main import create_app
from tests.test_task5a_pipeline import registry
from tests.test_verification_engine import handler as sources_handler

FIRST_FAILURES = [
    httpx.Response(503, json={"error": {"code": 503, "status": "UNAVAILABLE"}}),
    httpx.Response(
        429,
        json={
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [
                            {"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}
                        ],
                    },
                    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "3s"},
                ],
            }
        },
    ),
]


def _ok(obj):
    return httpx.Response(
        200,
        json={
            "candidates": [
                {"content": {"parts": [{"text": json.dumps(obj)}]}, "finishReason": "STOP"}
            ]
        },
    )


def _gemini(first_failure):
    calls = []

    def handle(request: httpx.Request):
        calls.append(request)
        if len(calls) == 1:
            return first_failure
        props = json.loads(request.content)["generationConfig"]["responseJsonSchema"]["properties"]
        if "claims" in props:
            return _ok({"claims": []})
        return _ok(
            ClassificationSuggestion(
                suggested_claim_type=ClaimType.QURAN, rationale="r"
            ).model_dump(mode="json")
        )

    async def nosleep(_s):
        return None

    p = GeminiProvider(
        api_key="test-key",
        model="gemini-3.5-flash-lite",
        transport=httpx.MockTransport(handle),
        sleep=nosleep,
    )
    return p, calls


def _client(provider):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[get_llm_provider] = lambda: provider
    app.dependency_overrides[get_registry] = lambda: registry(handler=sources_handler)
    return TestClient(app)


@pytest.mark.parametrize("first", FIRST_FAILURES)
def test_full_content_extraction_succeeds_on_first_user_attempt(first):
    p, calls = _gemini(first)
    r = _client(p).post("/api/v1/claims/extract", json={"text": "قال تعالى: «قل هو الله أحد»"})
    assert r.status_code == 200 and r.json()["kind"] == "extraction"
    assert len(calls) == 2  # one transient failure, one retry


@pytest.mark.parametrize("first", FIRST_FAILURES)
def test_verification_succeeds_on_first_user_attempt(first):
    p, calls = _gemini(first)
    claim = {
        "claim_id": "c1",
        "confirmed_claim_text": "قال تعالى في سورة البقرة: «إن الصفا والمروة من شعائر الله»",
        "user_confirmation_status": "confirmed",
    }
    r = _client(p).post("/api/v1/verify", json={"claims": [claim]})
    [o] = r.json()["outcomes"]
    assert o["kind"] == "verification" and o["status"] == "supported", o
    assert o["verified_reference"] == "سورة البقرة، الآية 158"
    assert len(calls) >= 2


@pytest.mark.parametrize("first", FIRST_FAILURES)
def test_alternative_wording_retries_a_transient_failure_and_is_still_reverified(first):
    """Production Quick Check scenario: wrong surah → contradicted → «اقترح صياغة بديلة».
    A transient Gemini failure on the alternative-wording call is retried (same provider path as
    extraction/verification), and the proposal is shown as verified only after re-verification."""
    calls = []
    failed = []
    wrong = "قال تعالى في سورة آل عمران: «إن الصفا والمروة من شعائر الله»"
    fixed = "قال تعالى في سورة البقرة: «إن الصفا والمروة من شعائر الله»"

    def handle(request: httpx.Request):
        calls.append(request)
        props = json.loads(request.content)["generationConfig"]["responseJsonSchema"]["properties"]
        if "proposed_claim_text" in props:
            if not failed:
                failed.append(1)
                return first
            return _ok({"proposed_claim_text": fixed, "rationale": "r"})
        return _ok(
            ClassificationSuggestion(
                suggested_claim_type=ClaimType.QURAN, rationale="r"
            ).model_dump(mode="json")
        )

    async def nosleep(_s):
        return None

    p = GeminiProvider(
        api_key="test-key",
        model="gemini-3.5-flash-lite",
        transport=httpx.MockTransport(handle),
        sleep=nosleep,
    )
    c = _client(p)
    claim = {
        "claim_id": "q1",
        "confirmed_claim_text": wrong,
        "user_confirmation_status": "confirmed",
    }
    v = c.post("/api/v1/verify", json={"claims": [claim]}).json()
    assert v["outcomes"][0]["status"] == "contradicted"
    r = c.post("/api/v1/alternative-wording", json={"run_id": v["run_id"], "claim_id": "q1"})
    assert r.status_code == 200, r.json()
    body = r.json()
    assert failed == [1]  # the transient failure happened and was retried
    assert body["proposed_text"] == fixed and body["verified"] is True
    assert body["outcome"]["status"] == "supported"
    assert body["outcome"]["verified_reference"] == "سورة البقرة، الآية 158"


def test_alternative_wording_daily_quota_is_not_retried_and_nothing_unverified_is_returned():
    daily = httpx.Response(
        429,
        json={
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [
                            {"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}
                        ],
                    }
                ],
            }
        },
    )
    alt_calls = []

    def handle(request: httpx.Request):
        props = json.loads(request.content)["generationConfig"]["responseJsonSchema"]["properties"]
        if "proposed_claim_text" in props:
            alt_calls.append(1)
            return daily
        return _ok(
            ClassificationSuggestion(
                suggested_claim_type=ClaimType.QURAN, rationale="r"
            ).model_dump(mode="json")
        )

    p = GeminiProvider(api_key="test-key", model="m", transport=httpx.MockTransport(handle))
    c = _client(p)
    claim = {
        "claim_id": "q1",
        "confirmed_claim_text": "قال تعالى في سورة آل عمران: «إن الصفا والمروة من شعائر الله»",
        "user_confirmation_status": "confirmed",
    }
    v = c.post("/api/v1/verify", json={"claims": [claim]}).json()
    r = c.post("/api/v1/alternative-wording", json={"run_id": v["run_id"], "claim_id": "q1"})
    assert r.status_code == 502 and alt_calls == [1]
    assert r.json()["error"]["code"] == "llm_rate_limited"
    assert "proposed_text" not in r.json()
