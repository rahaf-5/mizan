"""Provider-neutral OCR contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field


class OcrImage(BaseModel):
    """A validated image ready for OCR."""

    model_config = ConfigDict(frozen=True)

    content: bytes
    mime_type: str
    width: int
    height: int


class ProviderWord(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    confidence: float | None = Field(default=None, ge=0, le=1)


class ProviderOcrResult(BaseModel):
    """What a provider adapter returns: raw text exactly as the provider gave it,
    plus any confidence information the provider genuinely exposes."""

    model_config = ConfigDict(frozen=True)

    text: str
    words: list[ProviderWord] = Field(default_factory=list)
    page_confidences: list[float] = Field(default_factory=list)
    detected_languages: list[str] = Field(default_factory=list)


class OcrProvider(ABC):
    """An OCR backend. Must raise MizanError subclasses (OcrProviderError,
    OcrTimeoutError, OcrNotConfiguredError) for technical failures — never
    return fabricated or "best guess" text."""

    name: str

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    async def extract_text(self, image: OcrImage) -> ProviderOcrResult: ...
