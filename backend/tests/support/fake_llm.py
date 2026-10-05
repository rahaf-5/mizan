"""Deterministic provider for tests: returns pre-queued outputs."""

from __future__ import annotations

from collections import deque

from app.llm.base import LLMProvider, LLMRequest, T
from app.llm.schemas import LLMOutput


class FakeLLMProvider(LLMProvider):
    name = "fake"

    def __init__(self, outputs: list[LLMOutput] | None = None) -> None:
        self._queue: deque[LLMOutput] = deque(outputs or [])
        self.requests: list[LLMRequest] = []

    def enqueue(self, output: LLMOutput) -> None:
        self._queue.append(output)

    async def generate_structured(self, request: LLMRequest, output_type: type[T]) -> T:
        self.check_output_type(request, output_type)
        self.requests.append(request)
        if not self._queue:
            raise LookupError("FakeLLMProvider has no queued output")
        out = self._queue.popleft()
        if not isinstance(out, output_type):
            raise TypeError(
                f"queued output is {type(out).__name__}, expected {output_type.__name__}"
            )
        return out
