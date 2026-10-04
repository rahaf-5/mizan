"""Select the configured LLM provider."""

from __future__ import annotations

from app.llm.base import LLMProvider


def build_llm_provider(settings) -> LLMProvider | None:  # type: ignore[no-untyped-def]
    name = settings.llm_provider
    if name == "none":
        return None
    if name == "fake":
        from app.llm.fake import FakeLLMProvider

        return FakeLLMProvider()
    if name == "anthropic":
        from app.llm.anthropic import AnthropicProvider

        key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
        return AnthropicProvider(api_key=key, model=settings.llm_model)
    raise ValueError(f"unknown LLM provider: {name}")  # pragma: no cover - validated by Settings
