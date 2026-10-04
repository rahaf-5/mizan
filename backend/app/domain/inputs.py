"""User input models (spec §2).

MVP input is TEXT ONLY (Quick Check and Full Content Check). Image input and
OCR are out of MVP scope (spec change log 2026-10-04).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import CheckMode, InputType


class ExtractionInput(BaseModel):
    """Text that is allowed to enter Claim Extraction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: CheckMode
    input_type: InputType = InputType.TEXT
    text: str = Field(min_length=1)
