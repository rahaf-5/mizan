"""Gemini adapter: request shape, strict output validation, error mapping, no secret leakage.

All HTTP is mocked; no real network or key is used.
"""

from __future__ import annotations

import json
import logging

import httpx
import pytest

from app.config import Settings
from app.domain.errors import (
    LLMAuthError,
    LLMContentBlockedError,
    LLMInvalidResponseError,
    LLMNotConfiguredError,
    LLMProviderError,
    LLMRateLimitedError,
    LLMTimeoutError,
)
from app.llm.base import LLMRequest
from app.llm.factory import build_llm_provider
from app.llm.gemini import BASE_URL, GeminiProvider
from app.llm.schemas import ClaimExtractionDraft, ClassificationSuggestion, LLMTask

KEY = "TEST" + "k" * 35  # synthetic
REQ = LLMRequest(task=LLMTask.CLAIM_EXTRACTION, system_prompt="SYS", user_content="CONTENT")
GOOD = {
    "claims": [
        {"extracted_claim_text": "ادعاء", "source_excerpt": "ادعاء", "extraction_status": "clear"}
    ]
}


@pytest.fixture
def logs(caplog):
    lg = logging.getLogger("mizan")
    old = lg.propagate
    lg.propagate = True
    caplog.set_level(logging.INFO, logger="mizan")
    yield caplog
    lg.propagate = old


def ok_response(obj, finish="STOP", extra_parts=()):
    return {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [*extra_parts, {"text": json.dumps(obj, ensure_ascii=False)}],
                },
                "finishReason": finish,
            }
        ]
    }


def provider(handler, **kw):
    return GeminiProvider(
        api_key=KEY, model="gemini-3.5-flash-lite", transport=httpx.MockTransport(handler), **kw
    )


async def test_request_shape_and_header_auth():
    seen = {}

    def handler(r: httpx.Request):
        seen["url"], seen["headers"], seen["body"] = str(r.url), r.headers, json.loads(r.content)
        return httpx.Response(200, json=ok_response(GOOD))

    out = await provider(handler, thinking_level="low").generate_structured(
        REQ, ClaimExtractionDraft
    )
    assert out.claims[0].extracted_claim_text == "ادعاء"
    assert seen["url"] == f"{BASE_URL}/models/gemini-3.5-flash-lite:generateContent"
    assert KEY not in seen["url"] and seen["headers"]["x-goog-api-key"] == KEY
    body = seen["body"]
    assert body["system_instruction"]["parts"][0]["text"] == "SYS"
    assert body["contents"][0]["parts"][0]["text"] == "CONTENT"
    fmt = body["generationConfig"]["responseFormat"]["text"]
    assert fmt["mimeType"] == "application/json"
    assert "$defs" not in json.dumps(fmt["schema"]) and "claims" in fmt["schema"]["properties"]
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}


async def test_thought_parts_are_ignored():
    def handler(r):
        return httpx.Response(
            200, json=ok_response(GOOD, extra_parts=[{"text": "thinking...", "thought": True}])
        )

    out = await provider(handler).generate_structured(REQ, ClaimExtractionDraft)
    assert len(out.claims) == 1


async def test_output_type_must_match_task():
    with pytest.raises(TypeError):
        await provider(lambda r: httpx.Response(200)).generate_structured(
            REQ, ClassificationSuggestion
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"candidates": [{"content": {"parts": [{"text": "not json"}]}, "finishReason": "STOP"}]},
        ok_response({"claims": [{"extracted_claim_text": "x"}]}),  # missing required fields
        ok_response({"claims": [], "verdict": "true"}),  # extra field forbidden
        ok_response({"claims": [{**GOOD["claims"][0], "grading": "صحيح"}]}),  # no gradings allowed
        ok_response(GOOD, finish="MAX_TOKENS"),
        {"candidates": []},
        {"candidates": [{"content": {"parts": []}, "finishReason": "STOP"}]},
    ],
)
async def test_malformed_output_is_invalid_response(payload):
    with pytest.raises(LLMInvalidResponseError):
        await provider(lambda r: httpx.Response(200, json=payload)).generate_structured(
            REQ, ClaimExtractionDraft
        )


async def test_non_json_200_is_invalid_response():
    with pytest.raises(LLMInvalidResponseError):
        await provider(lambda r: httpx.Response(200, content=b"<html>")).generate_structured(
            REQ, ClaimExtractionDraft
        )


@pytest.mark.parametrize("finish", ["SAFETY", "PROHIBITED_CONTENT", "RECITATION", "BLOCKLIST"])
async def test_blocked_generation(finish):
    with pytest.raises(LLMContentBlockedError):
        await provider(
            lambda r: httpx.Response(200, json=ok_response(GOOD, finish=finish))
        ).generate_structured(REQ, ClaimExtractionDraft)


async def test_blocked_prompt():
    payload = {"promptFeedback": {"blockReason": "SAFETY"}}
    with pytest.raises(LLMContentBlockedError):
        await provider(lambda r: httpx.Response(200, json=payload)).generate_structured(
            REQ, ClaimExtractionDraft
        )


def err(code, status, reason=None, message="msg"):
    details = (
        [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": reason}] if reason else []
    )
    return httpx.Response(
        code,
        json={"error": {"code": code, "status": status, "message": message, "details": details}},
    )


@pytest.mark.parametrize(
    "response,exc,retryable",
    [
        (
            err(400, "INVALID_ARGUMENT", "API_KEY_INVALID", "API key not valid."),
            LLMAuthError,
            False,
        ),
        (err(401, "UNAUTHENTICATED"), LLMAuthError, False),
        (err(403, "PERMISSION_DENIED"), LLMAuthError, False),
        (err(429, "RESOURCE_EXHAUSTED"), LLMRateLimitedError, True),
        (err(404, "NOT_FOUND", message="models/x is not found"), LLMProviderError, False),
        (err(400, "INVALID_ARGUMENT", message="bad field"), LLMProviderError, False),
        (err(500, "INTERNAL"), LLMProviderError, True),
        (err(503, "UNAVAILABLE"), LLMProviderError, True),
        (err(504, "DEADLINE_EXCEEDED"), LLMTimeoutError, True),
        (httpx.Response(502, content=b"bad gateway"), LLMProviderError, True),
    ],
)
async def test_http_errors_are_mapped(response, exc, retryable, logs):
    with pytest.raises(exc) as e:
        await provider(lambda r: response).generate_structured(REQ, ClaimExtractionDraft)
    assert e.value.retryable is retryable
    assert (
        "Gemini rejected the request" in logs.text
        and KEY not in logs.text
        and KEY not in str(e.value)
    )


async def test_timeout_and_network_errors():
    def slow(r):
        raise httpx.ReadTimeout("slow", request=r)

    def down(r):
        raise httpx.ConnectError("down", request=r)

    with pytest.raises(LLMTimeoutError):
        await provider(slow).generate_structured(REQ, ClaimExtractionDraft)
    with pytest.raises(LLMProviderError) as e:
        await provider(down).generate_structured(REQ, ClaimExtractionDraft)
    assert e.value.retryable is True


async def test_missing_key_never_calls_provider():
    calls = []
    p = GeminiProvider(
        api_key=None, model="m", transport=httpx.MockTransport(lambda r: calls.append(r))
    )
    with pytest.raises(LLMNotConfiguredError):
        await p.generate_structured(REQ, ClaimExtractionDraft)
    assert calls == [] and not p.is_configured()


def test_factory_rejects_invisible_characters_in_key():
    p = build_llm_provider(Settings(llm_provider="gemini", gemini_api_key="‏" + KEY))
    assert p is not None and not p.is_configured()
    assert "U+200F RIGHT-TO-LEFT MARK at position 0" in (p.config_problem or "")
    assert KEY not in (p.config_problem or "")


def test_factory_uses_configured_model():
    p = build_llm_provider(
        Settings(llm_provider="gemini", gemini_api_key=KEY, gemini_model="gemini-x")
    )
    assert p.model == "gemini-x"


async def test_content_never_logged(logs):
    secret_text = "نص المستخدم الخاص جدا"
    req = LLMRequest(task=LLMTask.CLAIM_EXTRACTION, system_prompt="S", user_content=secret_text)
    with pytest.raises(LLMInvalidResponseError):
        await provider(
            lambda r: httpx.Response(200, json=ok_response({"claims": [{"x": secret_text}]}))
        ).generate_structured(req, ClaimExtractionDraft)
    assert secret_text not in logs.text
