"""User input models (spec §2).

MVP input is TEXT ONLY (Quick Check and Full Content Check). Image input and
OCR are out of MVP scope (spec change log 2026-10-04).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import CheckMode, InputType

#: Maximum characters accepted for claim extraction (MVP implementation limit;
#: protects free-tier LLM quota and keeps review manageable).
MAX_EXTRACTION_INPUT_CHARS: int = 10_000
#: Maximum characters for a single claim on Claim Review.
MAX_CLAIM_CHARS: int = 1_000
#: Maximum claims handled on one Claim Review screen.
MAX_REVIEW_CLAIMS: int = 50


class ExtractionInput(BaseModel):
    """Text that is allowed to enter Claim Extraction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: CheckMode
    input_type: InputType = InputType.TEXT
    text: str = Field(min_length=1, max_length=MAX_EXTRACTION_INPUT_CHARS)
