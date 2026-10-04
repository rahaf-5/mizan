from __future__ import annotations

from app.ocr.base import OcrProvider
from app.ocr.service import OcrService


def build_ocr_provider(settings) -> OcrProvider | None:  # type: ignore[no-untyped-def]
    if settings.ocr_provider == "google_vision":
        from app.ocr.google_vision import GoogleVisionOcrProvider

        key = settings.google_vision_api_key
        return GoogleVisionOcrProvider(
            api_key=key.get_secret_value() if key else None,
            timeout_seconds=settings.ocr_request_timeout_seconds,
            language_hints=settings.ocr_language_hint_list,
        )
    return None


def build_ocr_service(settings) -> OcrService | None:  # type: ignore[no-untyped-def]
    provider = build_ocr_provider(settings)
    if provider is None:
        return None
    return OcrService(provider, low_confidence_threshold=settings.ocr_low_confidence_threshold)
