"""Anthropic provider — PLANNED first adapter, intentionally NOT wired in Task 1.

The Anthropic SDK is not a dependency yet. When implemented, this adapter
must return only the requested LLMOutput subclass (validated), never Evidence.
"""

from __future__ import annotations

from app.domain.errors import LLMProviderError
from app.llm.base import LLMProvider, LLMRequest, T


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, *, api_key: str | None, model: str | None) -> None:
        self._api_key = api_key
        self._model = model

    async def generate_structured(self, request: LLMRequest, output_type: type[T]) -> T:
        self.check_output_type(request, output_type)
        raise LLMProviderError("Anthropic provider is planned but not wired yet (later task)")
