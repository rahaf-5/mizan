"""OCR models (spec §16, Task 3).

Flow: original image -> raw OCR output -> user-reviewed OCR text -> Claim Extraction.

OCR only extracts text. It never judges religious content, extracts claims,
verifies, generates evidence, or rewrites text. Raw OCR text is kept exactly
as returned by the provider; the user's reviewed text is stored separately.
OCR confidence is a reading-quality signal only — never verification confidence.
OCR technical failures are system errors, never a VerificationStatus.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import _StrEnum
from app.domain.errors import SystemErrorInfo

#: User-facing upload limit (LOCKED in Task 3): 7 MB, JPG/PNG.
#: Rationale: Google Cloud Vision limits JSON requests to 10 MB; inline images
#: are base64-encoded (+~33%), so 7 MiB (≈9.8 MB encoded) fits with headroom.
MAX_UPLOAD_BYTES: int = 7 * 1024 * 1024
ACCEPTED_IMAGE_MIME_TYPES: tuple[str, ...] = ("image/jpeg", "image/png")
#: Google Cloud Vision OCR pixel cap (length x width), from official docs.
MAX_IMAGE_PIXELS: int = 75_000_000
#: Google's documented general minimum for accurate detection (about 640x480).
RECOMMENDED_MIN_PIXELS: int = 640 * 480


class OcrStatus(_StrEnum):
    """Outcome of a technically successful OCR run (failures are OcrFailure)."""

    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    NO_TEXT_FOUND = "no_text_found"


class OcrWarningCode(_StrEnum):
    #: Provider reported words below the configured confidence threshold.
    LOW_CONFIDENCE_TEXT = "low_confidence_text"
    #: Image is below the provider's documented recommended resolution.
    LOW_RESOLUTION_IMAGE = "low_resolution_image"


class OcrInputErrorCode(_StrEnum):
    """Problems with the uploaded file (user input), not technical failures."""

    UNSUPPORTED_TYPE = "unsupported_type"
    EMPTY_FILE = "empty_file"
    FILE_TOO_LARGE = "file_too_large"
    UNREADABLE_IMAGE = "unreadable_image"
    IMAGE_TOO_MANY_PIXELS = "image_too_many_pixels"


class OcrWarning(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: OcrWarningCode
    detail: str | None = None


class LowConfidenceWord(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    confidence: float = Field(ge=0, le=1)


class OcrConfidence(BaseModel):
    """Provider-reported reading confidence. Present ONLY if the provider exposes it."""

    model_config = ConfigDict(frozen=True)

    #: Mean of provider page confidences (0–1), if provided.
    page_confidence: float | None = Field(default=None, ge=0, le=1)
    word_count: int = Field(ge=0)
    low_confidence_threshold: float = Field(ge=0, le=1)
    low_confidence_word_count: int = Field(ge=0)
    #: Sample of low-confidence words (capped) to help the user review.
    low_confidence_words: list[LowConfidenceWord] = Field(default_factory=list)


class OcrImageInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    mime_type: str
    size_bytes: int = Field(ge=1)
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class OcrExtraction(BaseModel):
    """Technically successful OCR. `raw_text` is exactly what the provider returned."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["extraction"] = "extraction"
    ocr_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    provider: str = Field(min_length=1)
    status: OcrStatus
    raw_text: str
    warnings: list[OcrWarning] = Field(default_factory=list)
    confidence: OcrConfidence | None = None
    detected_languages: list[str] = Field(default_factory=list)
    image: OcrImageInfo
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _status_consistent(self) -> OcrExtraction:
        empty = not self.raw_text.strip()
        if empty != (self.status == OcrStatus.NO_TEXT_FOUND):
            raise ValueError("no_text_found iff raw_text has no usable text")
        if self.status == OcrStatus.COMPLETED and self.warnings:
            raise ValueError("completed results carry no warnings; use completed_with_warnings")
        if self.status == OcrStatus.COMPLETED_WITH_WARNINGS and not self.warnings:
            raise ValueError("completed_with_warnings requires at least one warning")
        return self


class OcrFailure(BaseModel):
    """OCR could not run (technical/system problem). Never a verification status."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["failure"] = "failure"
    provider: str
    error: SystemErrorInfo


OcrOutcome = Annotated[OcrExtraction | OcrFailure, Field(discriminator="kind")]


class ReviewedOcrText(BaseModel):
    """User-reviewed OCR text — the ONLY OCR-derived text Claim Extraction may receive.

    Keeps the raw OCR text unchanged next to the reviewed version.
    """

    model_config = ConfigDict(frozen=True)

    ocr_id: str
    provider: str
    raw_text: str
    reviewed_text: str = Field(min_length=1)

    @property
    def edited_by_user(self) -> bool:
        return self.reviewed_text != self.raw_text

    @model_validator(mode="after")
    def _reviewed_not_blank(self) -> ReviewedOcrText:
        if not self.reviewed_text.strip():
            raise ValueError("reviewed_text must not be empty")
        return self
