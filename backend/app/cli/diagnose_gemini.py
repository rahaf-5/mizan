"""Gemini request diagnostics — isolates which request feature the API rejects.

    cd backend && python -m app.cli.diagnose_gemini

Sends a short, public, harmless Arabic sentence through a ladder of requests,
adding ONE feature at a time, and prints for each: HTTP status, Google status,
message and field violations. Never prints the API key, prompts or content
(only lengths). Uses LLM settings from backend/.env (GEMINI_API_KEY, GEMINI_MODEL).

Ladder:
  0   model metadata (models.get)        — is the model callable with this key/API version?
  A   minimal generateContent            — contents only
  A2  + system_instruction
  B   + responseMimeType=application/json
  C1  + responseJsonSchema (trivial schema)
  C2  + responseJsonSchema (Mizan claim-extraction schema)
  C3* schema keyword isolation (only if C1 passes and C2 fails)
  D1  thinkingConfig.thinkingLevel=LOW   (no JSON)
  D2  thinkingConfig.thinkingLevel=low   (no JSON)
  E   full production request exactly as the adapter sends it
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from app.core_logging import redact
from app.llm.base import LLMRequest
from app.llm.gemini import (
    BASE_URL,
    GeminiProvider,
    _error_summary,
    field_violations,
    redacted_structure,
)
from app.llm.json_schema import inline_schema
from app.llm.prompts.claim_extraction import build_prompt
from app.llm.schemas import ClaimExtractionDraft, LLMTask

SENTENCE = "الصلاة عماد الدين."  # short, public, harmless
TRIVIAL_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "string"}},
    "required": ["ok"],
}


@dataclass
class StepResult:
    step: str
    label: str
    ok: bool
    http: int | None
    summary: str


# --- schema keyword isolation ------------------------------------------------------


def _walk(node: Any, fn: Callable[[dict], dict]) -> Any:
    if isinstance(node, dict):
        return fn({k: _walk(v, fn) for k, v in node.items()})
    if isinstance(node, list):
        return [_walk(v, fn) for v in node]
    return node


def without_keys(schema: dict, *keys: str) -> dict:
    return _walk(copy.deepcopy(schema), lambda d: {k: v for k, v in d.items() if k not in keys})


def without_nullable_anyof(schema: dict) -> dict:
    def fix(d: dict) -> dict:
        opts = d.get("anyOf")
        if isinstance(opts, list):
            non_null = [o for o in opts if not (isinstance(o, dict) and o.get("type") == "null")]
            if len(non_null) == 1:
                merged = {k: v for k, v in d.items() if k != "anyOf"}
                merged.update(non_null[0])
                return merged
        return d

    return _walk(copy.deepcopy(schema), fix)


SCHEMA_VARIANTS: list[tuple[str, str, Callable[[dict], dict]]] = [
    (
        "C3a",
        "schema without additionalProperties",
        lambda s: without_keys(s, "additionalProperties"),
    ),
    ("C3b", "schema without maxItems", lambda s: without_keys(s, "maxItems")),
    ("C3c", "schema without nullable anyOf", without_nullable_anyof),
    ("C3d", "schema without descriptions", lambda s: without_keys(s, "description")),
    ("C3e", "schema without enum", lambda s: without_keys(s, "enum")),
]


# --- request bodies ----------------------------------------------------------------


def _contents() -> list[dict]:
    return [{"role": "user", "parts": [{"text": SENTENCE}]}]


def body(generation: dict | None = None, system: bool = False) -> dict:
    b: dict[str, Any] = {"contents": _contents()}
    if system:
        b["system_instruction"] = {"parts": [{"text": "Answer briefly."}]}
    if generation:
        b["generationConfig"] = generation
    return b


def production_body(provider: GeminiProvider) -> dict:
    system_prompt, user_content = build_prompt(SENTENCE)
    req = LLMRequest(
        task=LLMTask.CLAIM_EXTRACTION, system_prompt=system_prompt, user_content=user_content
    )
    return provider._body(req, ClaimExtractionDraft)


# --- runner ------------------------------------------------------------------------


async def run_diagnostics(
    api_key: str,
    model: str,
    *,
    thinking_level: str = "low",
    transport: httpx.AsyncBaseTransport | None = None,
    delay: float = 4.0,
    out: Callable[[str], None] = print,
) -> dict[str, StepResult]:
    def say(text: str) -> None:
        out(redact(text, [api_key]))

    provider = GeminiProvider(api_key=api_key, model=model, thinking_level=thinking_level)
    schema = inline_schema(ClaimExtractionDraft)
    json_mime = {"responseMimeType": "application/json"}
    results: dict[str, StepResult] = {}
    headers = {"x-goog-api-key": api_key}
    url = f"{BASE_URL}/models/{model}:generateContent"

    say(f"model={model}  endpoint=v1beta generateContent  key=<set, {len(api_key)} chars>")
    say("production request structure (texts replaced by lengths):")
    prod = production_body(provider)
    shape = redacted_structure(prod)
    shape["generationConfig"]["responseJsonSchema"] = "<claim schema, see C2>"
    say("  " + json.dumps(shape, ensure_ascii=False))

    async with httpx.AsyncClient(timeout=45, transport=transport) as client:

        async def call(step: str, label: str, payload: dict | None) -> StepResult:
            if results:
                await asyncio.sleep(delay)
            try:
                if payload is None:
                    r = await client.get(f"{BASE_URL}/models/{model}", headers=headers)
                else:
                    r = await client.post(url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                res = StepResult(step, label, False, None, f"network error: {type(exc).__name__}")
                results[step] = res
                say(f"[{step:>3}] FAIL  {label}: {res.summary}")
                return res
            try:
                data = r.json()
            except ValueError:
                data = None
            if r.status_code == 200:
                if payload is None:
                    d = data or {}
                    summary = (
                        f"name={d.get('name')} version={d.get('version')} "
                        f"methods={d.get('supportedGenerationMethods')} "
                        f"in={d.get('inputTokenLimit')} out={d.get('outputTokenLimit')} "
                        f"thinking={d.get('thinking')}"
                    )
                else:
                    cand = ((data or {}).get("candidates") or [{}])[0]
                    parts = (cand.get("content") or {}).get("parts") or []
                    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                    is_json = False
                    try:
                        json.loads(text)
                        is_json = True
                    except ValueError:
                        pass
                    summary = (
                        f"finishReason={cand.get('finishReason')} answer_chars={len(text)} "
                        f"valid_json={is_json}"
                    )
                res = StepResult(step, label, True, 200, summary)
            else:
                status, reason, message = _error_summary(data)
                fv = "; ".join(field_violations(data)) or "none"
                summary = (
                    f"{status}"
                    + (f" ({reason})" if reason else "")
                    + f" message={message!r} field_violations={fv}"
                )
                res = StepResult(step, label, False, r.status_code, summary)
            results[step] = res
            tag = "OK  " if res.ok else "FAIL"
            say(f"[{step:>3}] {tag}  HTTP {res.http}  {label}: {res.summary}")
            return res

        await call("0", "model metadata (models.get)", None)
        await call("A", "minimal: contents only", body())
        await call("A2", "+ system_instruction", body(system=True))
        await call("B", "+ responseMimeType=application/json", body(json_mime))
        await call(
            "C1",
            "+ trivial responseJsonSchema",
            body({**json_mime, "responseJsonSchema": TRIVIAL_SCHEMA}),
        )
        c2 = await call(
            "C2", "+ Mizan claim schema", body({**json_mime, "responseJsonSchema": schema})
        )
        if results["C1"].ok and not c2.ok:
            for step, label, fn in SCHEMA_VARIANTS:
                await call(step, label, body({**json_mime, "responseJsonSchema": fn(schema)}))
        await call(
            "D1",
            "thinkingConfig.thinkingLevel=LOW",
            body({"thinkingConfig": {"thinkingLevel": "LOW"}}),
        )
        await call(
            "D2",
            "thinkingConfig.thinkingLevel=low",
            body({"thinkingConfig": {"thinkingLevel": "low"}}),
        )
        await call("E", "full production request", prod)

    say("")
    for line in conclusions(results):
        say(line)
    return results


def conclusions(r: dict[str, StepResult]) -> list[str]:
    ok = {k: v.ok for k, v in r.items()}
    lines = ["CONCLUSION:"]
    if not ok.get("0", False):
        lines.append(
            "- Model metadata request failed: model name / API version / key access problem."
        )
    if not ok.get("A", False):
        lines.append("- Even the minimal request fails: not a structured-output or thinking issue.")
        return lines
    lines.append("- Model is callable with this key (minimal request OK).")
    feats = [
        ("A2", "system_instruction"),
        ("B", "responseMimeType=application/json"),
        ("C1", "responseJsonSchema (trivial)"),
        ("C2", "responseJsonSchema (Mizan schema)"),
        ("D1", "thinkingLevel=LOW"),
        ("D2", "thinkingLevel=low"),
        ("E", "full production request"),
    ]
    for step, name in feats:
        if step in ok:
            lines.append(f"- {name}: {'accepted' if ok[step] else 'REJECTED'}")
    fixes = [s for s, _, _ in SCHEMA_VARIANTS if ok.get(s)]
    if fixes:
        labels = {s: lab for s, lab, _ in SCHEMA_VARIANTS}
        lines.append("- Schema accepted when: " + ", ".join(labels[s] for s in fixes))
    return lines


def main() -> int:
    from app.config import get_settings
    from app.secrets_check import describe_secret_problem

    s = get_settings()
    key = s.gemini_api_key.get_secret_value() if s.gemini_api_key else None
    if not key:
        print("GEMINI_API_KEY is not set in backend/.env")
        return 2
    problem = describe_secret_problem("GEMINI_API_KEY", key)
    if problem:
        print(problem)
        return 2
    results = asyncio.run(
        run_diagnostics(key, s.gemini_model, thinking_level=s.gemini_thinking_level or "low")
    )
    return 0 if results.get("E") and results["E"].ok else 1


if __name__ == "__main__":
    sys.exit(main())
