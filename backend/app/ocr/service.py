"""OCR service: validated image -> provider -> structured OcrExtraction.

Status/warnings are derived only from facts: whether usable text exists,
provider-reported confidences (when exposed), and documented resolution guidance.
"""

from __future__ import annotations

from app.domain.ocr import (
    RECOMMENDED_MIN_PIXELS,
    LowConfidenceWord,
    OcrConfidence,
    OcrExtraction,
    OcrImageInfo,
    OcrStatus,
    OcrWarning,
    OcrWarningCode,
)
from app.ocr.base import OcrImage, OcrProvider

MAX_LOW_CONFIDENCE_SAMPLES = 30


class OcrService:
    def __init__(self, provider: OcrProvider, *, low_confidence_threshold: float) -> None:
        self.provider = provider
        self._threshold = low_confidence_threshold

    async def extract(self, image: OcrImage) -> OcrExtraction:
        result = await self.provider.extract_text(image)  # raises on technical failure
        raw_text = result.text  # never modified
        warnings: list[OcrWarning] = []
        confidence: OcrConfidence | None = None

        scored = [w for w in result.words if w.confidence is not None and w.text.strip()]
        if scored or result.page_confidences:
            low = [w for w in scored if (w.confidence or 0) < self._threshold]
            confidence = OcrConfidence(
                page_confidence=(
                    sum(result.page_confidences) / len(result.page_confidences)
                    if result.page_confidences
                    else None
                ),
                word_count=len(scored),
                low_confidence_threshold=self._threshold,
                low_confidence_word_count=len(low),
                low_confidence_words=[
                    LowConfidenceWord(text=w.text, confidence=w.confidence or 0)
                    for w in low[:MAX_LOW_CONFIDENCE_SAMPLES]
                ],
            )
            if low and raw_text.strip():
                warnings.append(
                    OcrWarning(code=OcrWarningCode.LOW_CONFIDENCE_TEXT, detail=f"{len(low)} words")
                )

        if image.width * image.height < RECOMMENDED_MIN_PIXELS:
            warnings.append(OcrWarning(code=OcrWarningCode.LOW_RESOLUTION_IMAGE))

        if not raw_text.strip():
            status = OcrStatus.NO_TEXT_FOUND
        elif warnings:
            status = OcrStatus.COMPLETED_WITH_WARNINGS
        else:
            status = OcrStatus.COMPLETED

        if status == OcrStatus.NO_TEXT_FOUND:
            warnings = [w for w in warnings if w.code == OcrWarningCode.LOW_RESOLUTION_IMAGE]
            # no_text_found carries its own meaning; resolution hint may still help the user.

        return OcrExtraction(
            provider=self.provider.name,
            status=status,
            raw_text=raw_text,
            warnings=warnings,
            confidence=confidence,
            detected_languages=result.detected_languages,
            image=OcrImageInfo(
                mime_type=image.mime_type,
                size_bytes=len(image.content),
                width=image.width,
                height=image.height,
            ),
        )
