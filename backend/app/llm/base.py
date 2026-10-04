"""Provider-agnostic LLM interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel, ConfigDict

from app.llm.schemas import TASK_OUTPUT_SCHEMAS, LLMOutput, LLMTask

T = TypeVar("T", bound=LLMOutput)


class LLMRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    task: LLMTask
    system_prompt: str
    user_content: str


class LLMProvider(ABC):
    """An LLM backend. Returns only validated `LLMOutput` subclasses."""

    name: str

    def is_configured(self) -> bool:
        return True

    @property
    def config_problem(self) -> str | None:
        return None

    @abstractmethod
    async def generate_structured(self, request: LLMRequest, output_type: type[T]) -> T: ...

    @staticmethod
    def check_output_type(request: LLMRequest, output_type: type[LLMOutput]) -> None:
        expected = TASK_OUTPUT_SCHEMAS[request.task]
        if output_type is not expected:
            raise TypeError(
                f"task {request.task.value} must return {expected.__name__}, "
                f"not {output_type.__name__}"
            )
