"""User input models (spec §2, §16).

OCR rule: image text must be reviewed by the user before Claim Extraction.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import CheckMode, InputType


class ExtractionInput(BaseModel):
    """Text that is allowed to enter Claim Extraction."""

    model_config = ConfigDict(frozen=True)

    mode: CheckMode
    input_type: InputType
    text: str = Field(min_length=1)
    #: For image input: the user reviewed/corrected the OCR text (spec §16).
    ocr_text_reviewed_by_user: bool = False

    @model_validator(mode="after")
    def _ocr_must_be_reviewed(self) -> ExtractionInput:
        if self.input_type == InputType.IMAGE and not self.ocr_text_reviewed_by_user:
            raise ValueError("unreviewed OCR text must never reach claim extraction")
        if self.mode == CheckMode.QUICK_CHECK and self.input_type != InputType.TEXT:
            raise ValueError("Quick Check accepts a single text claim only")
        return self
