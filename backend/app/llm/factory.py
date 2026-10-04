"""Select the configured LLM provider (provider-neutral entry point)."""

from __future__ import annotations

from app.llm.base import LLMProvider
from app.secrets_check import describe_secret_problem


def build_llm_provider(settings) -> LLMProvider | None:  # type: ignore[no-untyped-def]
    if settings.llm_provider == "none":
        return None
    if settings.llm_provider == "gemini":
        from app.llm.gemini import GeminiProvider

        raw = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
        problem = describe_secret_problem("GEMINI_API_KEY", raw)
        return GeminiProvider(
            api_key=None if problem else raw,
            model=settings.gemini_model,
            timeout_seconds=settings.llm_request_timeout_seconds,
            thinking_level=settings.gemini_thinking_level,
            config_problem=problem,
        )
    raise ValueError(f"unknown LLM provider: {settings.llm_provider}")  # pragma: no cover
