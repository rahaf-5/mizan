"""Gemini Developer API adapter (current MVP LLM provider).

Infrastructure only: nothing outside app/llm imports this module. It
implements the provider-neutral `LLMProvider` contract and returns a
validated `LLMOutput` — never evidence, citations or gradings.

Official docs used (checked 2026-10-04):
  - POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
  - auth header `x-goog-api-key`
  - system_instruction / contents / generationConfig
  - structured output: generationConfig.responseMimeType = "application/json" +
    generationConfig.responseJsonSchema (the mechanism the official google-genai SDK uses for
    the Gemini Developer API; `responseFormat` is only sent by the SDK to Vertex AI and was
    rejected by this API with 400 INVALID_ARGUMENT on
    generation_config.response_format.text.mime_type — see tests/test_gemini_adapter.py)
  - thinking: generationConfig.thinkingConfig.thinkingLevel, sent as the canonical enum
    name (MINIMAL | LOW | MEDIUM | HIGH)
  - errors: 400/401/403/404/429/500/503/504; blocked generations (safety, recitation, …)
Logged: HTTP status, provider status/reason, sizes. Never logged: API key, content.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.core_logging import get_logger, redact
from app.domain.errors import (
    LLMAuthError,
    LLMContentBlockedError,
    LLMInvalidResponseError,
    LLMNotConfiguredError,
    LLMProviderError,
    LLMRateLimitedError,
    LLMTimeoutError,
)
from app.llm.base import LLMProvider, LLMRequest, T
from app.llm.json_schema import inline_schema

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_BLOCKED_FINISH = {
    "SAFETY",
    "RECITATION",
    "LANGUAGE",
    "PROHIBITED_CONTENT",
    "SPII",
    "BLOCKLIST",
    "IMAGE_SAFETY",
    "OTHER",
}
log = get_logger("llm.gemini")

# JSON-Schema keywords the Gemini Developer API rejects in `responseJsonSchema`.
# Live diagnostic (2026-10-04, gemini-3.5-flash-lite, v1beta): the full Mizan schema
# -> 400 INVALID_ARGUMENT; the identical schema without `maxItems` -> 200.
# Removing a keyword here ONLY relaxes the hint sent to Gemini. Every response is
# still validated by the Pydantic output model (e.g. claims max_length=50), so the
# application limits are enforced locally and unchanged.
GEMINI_UNSUPPORTED_SCHEMA_KEYS = frozenset({"maxItems"})


def gemini_response_schema(output_type: type[BaseModel]) -> dict[str, Any]:
    """Provider-neutral inline schema minus keywords Gemini rejects."""

    def strip(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: strip(v) for k, v in node.items() if k not in GEMINI_UNSUPPORTED_SCHEMA_KEYS}
        if isinstance(node, list):
            return [strip(v) for v in node]
        return node

    return strip(inline_schema(output_type))


def _error_summary(payload: Any) -> tuple[str, str | None, str]:
    err = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(err, dict):
        return "UNKNOWN", None, ""
    reason = None
    for d in err.get("details") or []:
        if isinstance(d, dict) and d.get("reason"):
            reason = str(d["reason"])
            break
    return (
        str(err.get("status") or err.get("code") or "UNKNOWN"),
        reason,
        str(err.get("message") or ""),
    )


def field_violations(payload: Any) -> list[str]:
    """`google.rpc.BadRequest.fieldViolations` as "field: description" (no content/key)."""
    err = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(err, dict):
        return []
    out: list[str] = []
    for d in err.get("details") or []:
        if isinstance(d, dict):
            for v in d.get("fieldViolations") or []:
                if isinstance(v, dict):
                    out.append(f"{v.get('field', '?')}: {v.get('description', '')}".strip())
    return out


def redacted_structure(body: Any) -> Any:
    """Request body with every `text` value replaced by its length (safe to print/log)."""
    if isinstance(body, dict):
        return {
            k: (
                f"<text: {len(v)} chars>"
                if k == "text" and isinstance(v, str)
                else redacted_structure(v)
            )
            for k, v in body.items()
        }
    if isinstance(body, list):
        return [redacted_structure(v) for v in body]
    return body


# --- transient-failure retry (provider level: every LLM task benefits) ------------------------
#: Total attempts per LLM call for transient provider failures (1 = no retry).
MAX_ATTEMPTS = 3
#: Short backoff when the provider does not say how long to wait.
BACKOFF_SECONDS = (1.5, 3.0)
#: Longest provider-requested wait we honour; longer means "quota", which retries cannot fix.
MAX_RETRY_DELAY_SECONDS = 30.0
#: Wall-clock budget for one LLM call including retries (frontend waits 90-180 s per request).
RETRY_BUDGET_SECONDS = 80.0
_TRANSIENT_HTTP = {429, 500, 502, 503, 504}
_DURATION = re.compile(r"^\s*(\d+(?:\.\d+)?)s\s*$")


def _is_daily_quota(payload: Any) -> bool:
    """429 from a per-day quota (e.g. ...PerDay...FreeTier): exhausted until reset; never retry."""
    err = payload.get("error") if isinstance(payload, dict) else None
    for d in (err.get("details") or []) if isinstance(err, dict) else []:
        for v in (d.get("violations") or []) if isinstance(d, dict) else []:
            if isinstance(v, dict) and "perday" in str(v.get("quotaId", "")).lower():
                return True
    return False


def _requested_delay(headers: httpx.Headers, payload: Any) -> float | None:
    """Retry-After header (seconds) or google.rpc.RetryInfo.retryDelay ("12s"), if given."""
    ra = headers.get("retry-after")
    if ra:
        try:
            return max(0.0, float(ra))
        except ValueError:
            pass
    err = payload.get("error") if isinstance(payload, dict) else None
    for d in (err.get("details") or []) if isinstance(err, dict) else []:
        if isinstance(d, dict) and isinstance(d.get("retryDelay"), str):
            m = _DURATION.match(d["retryDelay"])
            if m:
                return float(m.group(1))
    return None


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        timeout_seconds: float = 45,
        thinking_level: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
        config_problem: str | None = None,
        max_attempts: int = MAX_ATTEMPTS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._api_key = api_key or None
        self.model = model
        self._timeout = timeout_seconds
        self._thinking = thinking_level
        self._transport = transport
        self._config_problem = config_problem
        self._max_attempts = max(1, max_attempts)
        self._sleep = sleep

    @property
    def config_problem(self) -> str | None:
        if self._config_problem:
            return self._config_problem
        if not self._api_key:
            return "GEMINI_API_KEY is not set"
        return None

    def is_configured(self) -> bool:
        return self.config_problem is None

    def generation_config(self, output_type: type[T]) -> dict[str, Any]:
        """generationConfig sent to generateContent (also used by the diagnostic CLI)."""
        generation: dict[str, Any] = {
            "responseMimeType": "application/json",
            "responseJsonSchema": gemini_response_schema(output_type),
        }
        if self._thinking:
            generation["thinkingConfig"] = {"thinkingLevel": self._thinking.upper()}
        return generation

    def _body(self, request: LLMRequest, output_type: type[T]) -> dict:
        return {
            "system_instruction": {"parts": [{"text": request.system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": request.user_content}]}],
            "generationConfig": self.generation_config(output_type),
        }

    def _safe(self, text: str) -> str:
        return redact(text, [self._api_key])

    async def generate_structured(self, request: LLMRequest, output_type: type[T]) -> T:
        self.check_output_type(request, output_type)
        problem = self.config_problem
        if problem:
            log.warning("LLM not configured: %s", problem)
            raise LLMNotConfiguredError(problem)

        url = f"{BASE_URL}/models/{self.model}:generateContent"
        body = self._body(request, output_type)
        started = time.monotonic()
        attempt = 0
        while True:
            attempt += 1
            elapsed = time.monotonic() - started
            timeout = max(5.0, min(float(self._timeout), RETRY_BUDGET_SECONDS - elapsed))
            transient: str | None = None
            delay: float | None = None
            failure: Exception | None = None
            try:
                async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                    resp = await client.post(
                        url, json=body, headers={"x-goog-api-key": self._api_key or ""}
                    )
            except httpx.TimeoutException as exc:
                log.warning("Gemini timed out after %ss (task=%s)", timeout, request.task.value)
                failure = LLMTimeoutError("LLM provider timed out")
                failure.__cause__ = exc
                transient = "timeout"
            except httpx.HTTPError as exc:
                log.warning("Gemini unreachable: %s", type(exc).__name__)
                failure = LLMProviderError(f"LLM provider unreachable: {type(exc).__name__}")
                failure.__cause__ = exc
                transient = type(exc).__name__
            except (UnicodeError, ValueError, TypeError) as exc:
                log.error("Could not build Gemini request: %s", type(exc).__name__)
                raise LLMProviderError(
                    f"LLM request could not be built: {type(exc).__name__}"
                ) from exc
            else:
                try:
                    payload = resp.json()
                except ValueError:
                    payload = None
                if resp.status_code == 200:
                    return self._parse(payload, output_type, request)
                if resp.status_code in _TRANSIENT_HTTP and not (
                    resp.status_code == 429 and _is_daily_quota(payload)
                ):
                    transient = f"http {resp.status_code}"
                    delay = _requested_delay(resp.headers, payload)
                try:
                    self._raise_http_error(resp.status_code, payload)
                except LLMProviderError as exc:
                    failure = exc
            assert failure is not None
            # Retry only transient provider failures, within attempts and the time budget.
            if transient is None or attempt >= self._max_attempts:
                raise failure
            if delay is None:
                delay = BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)]
            if delay > MAX_RETRY_DELAY_SECONDS or (
                time.monotonic() - started + delay + 5.0 > RETRY_BUDGET_SECONDS
            ):
                raise failure
            log.warning(
                "Gemini transient failure (%s, task=%s); retry %d/%d in %.1fs",
                transient,
                request.task.value,
                attempt,
                self._max_attempts - 1,
                delay,
            )
            await self._sleep(delay)

    def _raise_http_error(self, status_code: int, payload: Any) -> None:
        status, reason, message = _error_summary(payload)
        violations = "; ".join(field_violations(payload)) or "none"
        log.warning(
            "Gemini rejected the request: http=%s status=%s reason=%s model=%s message=%s "
            "field_violations=%s",
            status_code,
            status,
            reason,
            self.model,
            self._safe(message),
            self._safe(violations),
        )
        summary = f"HTTP {status_code} {status}" + (f" ({reason})" if reason else "")
        if status_code in (401, 403) or reason in {"API_KEY_INVALID", "API_KEY_SERVICE_BLOCKED"}:
            raise LLMAuthError(f"LLM provider rejected the credentials: {summary}")
        if status_code == 429:
            raise LLMRateLimitedError(f"LLM provider rate limit or quota reached: {summary}")
        if status_code == 504:
            raise LLMTimeoutError(f"LLM provider deadline exceeded: {summary}")
        exc = LLMProviderError(f"LLM provider error: {summary}")
        exc.retryable = status_code >= 500
        raise exc

    def _parse(self, payload: Any, output_type: type[T], request: LLMRequest) -> T:
        if not isinstance(payload, dict):
            log.warning("Gemini returned a non-JSON 200 response")
            raise LLMInvalidResponseError("LLM provider returned an invalid response")
        block = (payload.get("promptFeedback") or {}).get("blockReason")
        if block:
            log.warning("Gemini blocked the prompt: blockReason=%s", block)
            raise LLMContentBlockedError(f"LLM provider blocked the content ({block})")
        candidates = payload.get("candidates") or []
        if not candidates or not isinstance(candidates[0], dict):
            log.warning("Gemini returned no candidates")
            raise LLMInvalidResponseError("LLM provider returned no result")
        cand = candidates[0]
        finish = str(cand.get("finishReason") or "")
        if finish in _BLOCKED_FINISH:
            log.warning("Gemini generation blocked: finishReason=%s", finish)
            raise LLMContentBlockedError(f"LLM provider blocked the generation ({finish})")
        if finish == "MAX_TOKENS":
            log.warning("Gemini output truncated (MAX_TOKENS)")
            raise LLMInvalidResponseError("LLM output was truncated")
        parts = ((cand.get("content") or {}).get("parts")) or []
        text = "".join(
            p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought")
        )
        if not text.strip():
            log.warning("Gemini returned an empty answer (finishReason=%s)", finish or "none")
            raise LLMInvalidResponseError("LLM provider returned an empty answer")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            log.warning("Gemini answer was not valid JSON (%d chars)", len(text))
            raise LLMInvalidResponseError("LLM output was not valid JSON") from exc
        try:
            return output_type.model_validate(data)
        except ValidationError as exc:
            fields = sorted({".".join(str(x) for x in e["loc"]) or "<root>" for e in exc.errors()})
            log.warning(
                "Gemini output failed validation for %s (fields: %s)",
                output_type.__name__,
                ", ".join(fields[:10]),
            )
            raise LLMInvalidResponseError(
                "LLM output did not match the required structure"
            ) from exc
