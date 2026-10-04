"""Diagnostic ladder for the second live 400 (generic INVALID_ARGUMENT).

Mocked HTTP only. Verifies the ladder isolates the rejected feature and that the
output never contains the API key, the prompt or the submitted content.
"""

from __future__ import annotations

import json
import logging

import httpx
import pytest

from app.cli.diagnose_gemini import (
    SENTENCE,
    conclusions,
    run_diagnostics,
    without_keys,
    without_nullable_anyof,
)
from app.llm.base import LLMRequest
from app.llm.gemini import GeminiProvider, field_violations, redacted_structure
from app.llm.json_schema import inline_schema
from app.llm.schemas import ClaimExtractionDraft, LLMTask

KEY = "DIAG" + "z" * 35
GENERIC_400 = {
    "error": {
        "code": 400,
        "message": "Request contains an invalid argument.",
        "status": "INVALID_ARGUMENT",
    }
}


def ok(text='{"ok":"x"}'):
    return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}


def make_handler(reject):
    """`reject(body)` -> True to answer with the generic 400."""

    def handler(r: httpx.Request):
        if r.method == "GET":
            return httpx.Response(
                200, json={"name": "models/m", "supportedGenerationMethods": ["generateContent"]}
            )
        body = json.loads(r.content)
        if reject(body):
            return httpx.Response(400, json=GENERIC_400)
        return httpx.Response(200, json=ok())

    return handler


async def diag(reject):
    lines: list[str] = []
    res = await run_diagnostics(
        KEY,
        "gemini-3.5-flash-lite",
        transport=httpx.MockTransport(make_handler(reject)),
        delay=0,
        out=lines.append,
    )
    return res, "\n".join(lines)


def gen(body):
    return body.get("generationConfig", {})


async def test_isolates_thinking_config():
    res, text = await diag(lambda b: "thinkingConfig" in gen(b))
    assert res["A"].ok and res["B"].ok and res["C2"].ok
    assert not res["D1"].ok and not res["D2"].ok and not res["E"].ok
    assert (
        "- thinkingLevel=LOW: REJECTED" in text
        and "- responseJsonSchema (Mizan schema): accepted" in text
    )


async def test_isolates_schema_keyword():
    def reject(b):
        return "additionalProperties" in json.dumps(gen(b).get("responseJsonSchema", {}))

    res, text = await diag(reject)
    assert res["C1"].ok and not res["C2"].ok
    assert res["C3a"].ok and not res["C3b"].ok
    assert "Schema accepted when: schema without additionalProperties" in text


async def test_isolates_json_mime_type():
    res, text = await diag(lambda b: "responseMimeType" in gen(b))
    assert res["A"].ok and not res["B"].ok and "C3a" not in res


async def test_minimal_failure_points_away_from_optional_features():
    res, text = await diag(lambda b: True)
    assert "Even the minimal request fails" in text


async def test_output_never_contains_key_prompt_or_content():
    _, text = await diag(lambda b: False)
    assert KEY not in text
    assert SENTENCE not in text
    assert "claim-extraction component" not in text  # system prompt never printed
    assert f"key=<set, {len(KEY)} chars>" in text


def test_redacted_structure_hides_texts():
    p = GeminiProvider(api_key=KEY, model="m", thinking_level="low")
    body = p._body(
        LLMRequest(
            task=LLMTask.CLAIM_EXTRACTION,
            system_prompt="SYSTEM SECRET PROMPT",
            user_content="نص المستخدم",
        ),
        ClaimExtractionDraft,
    )
    shape = json.dumps(redacted_structure(body), ensure_ascii=False)
    assert "SYSTEM SECRET PROMPT" not in shape and "نص المستخدم" not in shape and "<text:" in shape
    assert '"thinkingLevel": "LOW"' in shape


def test_schema_variants():
    schema = inline_schema(ClaimExtractionDraft)
    assert "additionalProperties" not in json.dumps(without_keys(schema, "additionalProperties"))
    flat = json.dumps(without_nullable_anyof(schema))
    assert "anyOf" not in flat and '"null"' not in flat


def test_field_violations_parsed():
    payload = {
        "error": {
            "status": "INVALID_ARGUMENT",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.BadRequest",
                    "fieldViolations": [
                        {
                            "field": "generation_config.thinking_config",
                            "description": "not supported",
                        }
                    ],
                }
            ],
        }
    }
    assert field_violations(payload) == ["generation_config.thinking_config: not supported"]
    assert field_violations(GENERIC_400) == []


@pytest.fixture
def logs(caplog):
    lg = logging.getLogger("mizan")
    old = lg.propagate
    lg.propagate = True
    caplog.set_level(logging.INFO, logger="mizan")
    yield caplog
    lg.propagate = old


async def test_adapter_logs_generic_400_with_field_violations(logs):
    from app.domain.errors import LLMProviderError

    payload = {
        "error": {
            "code": 400,
            "message": "Request contains an invalid argument.",
            "status": "INVALID_ARGUMENT",
            "details": [
                {"fieldViolations": [{"field": "generation_config", "description": "bad"}]}
            ],
        }
    }
    p = GeminiProvider(
        api_key=KEY,
        model="m",
        transport=httpx.MockTransport(lambda r: httpx.Response(400, json=payload)),
    )
    req = LLMRequest(task=LLMTask.CLAIM_EXTRACTION, system_prompt="s", user_content="u")
    with pytest.raises(LLMProviderError) as e:
        await p.generate_structured(req, ClaimExtractionDraft)
    assert e.value.retryable is False
    assert "field_violations=generation_config: bad" in logs.text and KEY not in logs.text


def test_conclusions_when_model_unavailable():
    from app.cli.diagnose_gemini import StepResult

    r = {
        "0": StepResult("0", "", False, 404, "NOT_FOUND"),
        "A": StepResult("A", "", False, 404, "NOT_FOUND"),
    }
    text = "\n".join(conclusions(r))
    assert "model name / API version / key access problem" in text
