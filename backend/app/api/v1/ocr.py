"""OCR endpoint: image -> raw OCR text for USER REVIEW.

It never extracts claims or verifies anything. The response is the raw OCR
result; the frontend must show it for review before anything else happens.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.core_logging import format_exception_safely, get_logger
from app.domain.enums import PipelineStage, SystemErrorCode
from app.domain.errors import MizanError, SystemErrorInfo
from app.domain.ocr import (
    ACCEPTED_IMAGE_MIME_TYPES,
    MAX_UPLOAD_BYTES,
    OcrExtraction,
    OcrFailure,
    OcrInputErrorCode,
)
from app.ocr.factory import build_ocr_service
from app.ocr.image_validation import OcrInputError, validate_image
from app.ocr.service import OcrService

router = APIRouter(prefix="/ocr", tags=["ocr"])
log = get_logger("api.ocr")


def _secrets(settings: Settings) -> list[str | None]:
    key = settings.google_vision_api_key
    return [key.get_secret_value() if key else None]


class OcrInputErrorResponse(BaseModel):
    kind: Literal["input_error"] = "input_error"
    code: OcrInputErrorCode
    message: str


class OcrLimits(BaseModel):
    max_upload_bytes: int
    accepted_mime_types: list[str]
    provider: str
    configured: bool


_HTTP_FOR_CODE = {
    SystemErrorCode.OCR_NOT_CONFIGURED: 503,
    SystemErrorCode.OCR_TIMEOUT: 504,
    SystemErrorCode.OCR_ERROR: 502,
}


def get_ocr_service(settings: Annotated[Settings, Depends(get_settings)]) -> OcrService | None:
    return build_ocr_service(settings)


@router.get("/limits", response_model=OcrLimits)
async def limits(settings: Annotated[Settings, Depends(get_settings)]) -> OcrLimits:
    service = build_ocr_service(settings)
    return OcrLimits(
        max_upload_bytes=MAX_UPLOAD_BYTES,
        accepted_mime_types=list(ACCEPTED_IMAGE_MIME_TYPES),
        provider=settings.ocr_provider,
        configured=bool(service and service.provider.is_configured()),
    )


@router.post(
    "",
    response_model=OcrExtraction,
    responses={
        400: {"model": OcrInputErrorResponse},
        413: {"model": OcrInputErrorResponse},
        502: {"model": OcrFailure},
        503: {"model": OcrFailure},
        504: {"model": OcrFailure},
    },
)
async def run_ocr(
    service: Annotated[OcrService | None, Depends(get_ocr_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    image: Annotated[UploadFile, File(description="JPG or PNG image")],
):
    data = await image.read(MAX_UPLOAD_BYTES + 1)
    try:
        validated = validate_image(data)
    except OcrInputError as exc:
        status = 413 if exc.code == OcrInputErrorCode.FILE_TOO_LARGE else 400
        body = OcrInputErrorResponse(code=exc.code, message=str(exc))
        return JSONResponse(status_code=status, content=body.model_dump(mode="json"))

    provider_name = settings.ocr_provider
    if service is None or not service.provider.is_configured():
        problem = getattr(service.provider, "config_problem", None) if service else None
        log.warning("OCR request refused: provider not configured (%s)", problem or provider_name)
        failure = OcrFailure(
            provider=provider_name,
            error=SystemErrorInfo(
                code=SystemErrorCode.OCR_NOT_CONFIGURED,
                stage=PipelineStage.USER_INPUT,
                message=problem or "OCR service is not configured",
                retryable=False,
            ),
        )
        return JSONResponse(status_code=503, content=failure.model_dump(mode="json"))

    try:
        return await service.extract(validated)
    except MizanError as exc:
        info = exc.to_info()
        log.warning("OCR failed: code=%s message=%s", info.code.value, info.message)
        failure = OcrFailure(provider=service.provider.name, error=info)
        return JSONResponse(
            status_code=_HTTP_FOR_CODE.get(info.code, 500), content=failure.model_dump(mode="json")
        )
    except Exception as exc:  # noqa: BLE001 - technical failure, never content judgement
        log.error(
            "Unexpected OCR error (internal_error):\n%s",
            format_exception_safely(exc, _secrets(settings)),
        )
        failure = OcrFailure(
            provider=service.provider.name,
            error=SystemErrorInfo(
                code=SystemErrorCode.INTERNAL_ERROR,
                stage=PipelineStage.USER_INPUT,
                message=type(exc).__name__,
            ),
        )
        return JSONResponse(status_code=500, content=failure.model_dump(mode="json"))
