"""Claim Extraction + Claim Confirmation endpoints (Task 4).

  POST /api/v1/claims/extract  — LLM-assisted extraction; returns PENDING claims for review.
  POST /api/v1/claims/confirm  — explicit user confirmation through the domain gate;
                                 returns ConfirmedClaims prepared for the future pipeline.

Neither endpoint verifies, retrieves evidence or produces any verdict.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings, get_settings
from app.core_logging import format_exception_safely, get_logger
from app.domain.claim import Claim, ConfirmedClaim, ProvidedEvidence, select_confirmed_claims
from app.domain.enums import (
    CheckMode,
    ExtractionStatus,
    PipelineStage,
    SystemErrorCode,
    UserConfirmationStatus,
)
from app.domain.errors import ClaimNotConfirmedError, MizanError, SystemErrorInfo
from app.domain.inputs import (
    MAX_CLAIM_CHARS,
    MAX_EXTRACTION_INPUT_CHARS,
    MAX_REVIEW_CLAIMS,
    ExtractionInput,
)
from app.llm.base import LLMProvider
from app.llm.factory import build_llm_provider
from app.pipeline.claim_extraction import LlmClaimExtractor

router = APIRouter(prefix="/claims", tags=["claims"])
log = get_logger("api.claims")


_HTTP_FOR_CODE = {
    SystemErrorCode.LLM_NOT_CONFIGURED: 503,
    SystemErrorCode.LLM_AUTH_FAILED: 503,
    SystemErrorCode.LLM_RATE_LIMITED: 429,
    SystemErrorCode.LLM_TIMEOUT: 504,
    SystemErrorCode.LLM_INVALID_RESPONSE: 502,
    SystemErrorCode.LLM_CONTENT_BLOCKED: 422,
    SystemErrorCode.LLM_PROVIDER_ERROR: 502,
}

# User-facing messages are generic; provider internals stay in the server log.
_PUBLIC_MESSAGE = {
    SystemErrorCode.LLM_NOT_CONFIGURED: "Claim extraction service is not configured",
    SystemErrorCode.LLM_AUTH_FAILED: "Claim extraction service is not available",
    SystemErrorCode.LLM_RATE_LIMITED: "Claim extraction service is busy; try again later",
    SystemErrorCode.LLM_TIMEOUT: "Claim extraction timed out",
    SystemErrorCode.LLM_INVALID_RESPONSE: "Claim extraction returned an unusable result",
    SystemErrorCode.LLM_CONTENT_BLOCKED: "The content could not be processed for extraction",
    SystemErrorCode.LLM_PROVIDER_ERROR: "Claim extraction service error",
}


def get_llm_provider(settings: Annotated[Settings, Depends(get_settings)]) -> LLMProvider | None:
    return build_llm_provider(settings)


def _secrets(settings: Settings) -> list[str | None]:
    key = settings.gemini_api_key
    return [key.get_secret_value() if key else None]


# --- schemas -------------------------------------------------------------------


class InputErrorResponse(BaseModel):
    kind: Literal["input_error"] = "input_error"
    code: str
    message: str


class FailureResponse(BaseModel):
    kind: Literal["failure"] = "failure"
    error: SystemErrorInfo


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str


class ProvidedEvidenceOut(BaseModel):
    provided_evidence_type: str
    provided_evidence_text: str


class ExtractedClaimOut(BaseModel):
    claim_id: str
    original_text: str
    extracted_claim_text: str
    extraction_status: ExtractionStatus
    provided_evidence: ProvidedEvidenceOut | None = None
    provided_reference: str | None = None
    user_confirmation_status: UserConfirmationStatus


class ExtractResponse(BaseModel):
    kind: Literal["extraction"] = "extraction"
    claims: list[ExtractedClaimOut]
    discarded_ungrounded_count: int = 0


class ReviewedClaimIn(BaseModel):
    """A claim as the user left it on the Claim Review screen."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, max_length=100)
    origin: Literal["extracted", "manual"]
    original_text: str = Field(default="", max_length=4000)
    extracted_claim_text: str | None = Field(default=None, max_length=MAX_CLAIM_CHARS)
    #: The text the user is confirming (edited text if they edited it).
    text: str = Field(max_length=MAX_CLAIM_CHARS)
    selected: bool
    extraction_status: ExtractionStatus | None = None
    provided_evidence: ProvidedEvidence | None = None
    provided_reference: str | None = Field(default=None, max_length=500)


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Must be true: set only by the user's explicit click on «تحقّق من الادعاءات المحددة».
    explicit_user_confirmation: bool
    claims: list[ReviewedClaimIn] = Field(max_length=MAX_REVIEW_CLAIMS)


class ConfirmResponse(BaseModel):
    kind: Literal["confirmed"] = "confirmed"
    confirmed_claims: list[ConfirmedClaim]
    #: Next stage for Task 5+. Verification has NOT started.
    next_stage: Literal["claim_classification"] = "claim_classification"
    verification_started: Literal[False] = False


def _input_error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=InputErrorResponse(code=code, message=message).model_dump(mode="json"),
    )


def _failure(status: int, info: SystemErrorInfo) -> JSONResponse:
    return JSONResponse(
        status_code=status, content=FailureResponse(error=info).model_dump(mode="json")
    )


# --- extraction ----------------------------------------------------------------


@router.post(
    "/extract",
    response_model=ExtractResponse,
    responses={
        400: {"model": InputErrorResponse},
        413: {"model": InputErrorResponse},
        429: {"model": FailureResponse},
        502: {"model": FailureResponse},
        503: {"model": FailureResponse},
        504: {"model": FailureResponse},
    },
)
async def extract_claims(
    body: ExtractRequest,
    provider: Annotated[LLMProvider | None, Depends(get_llm_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    if not body.text.strip():
        return _input_error(400, "empty_text", "content text is empty")
    if len(body.text) > MAX_EXTRACTION_INPUT_CHARS:
        return _input_error(413, "text_too_long", f"maximum is {MAX_EXTRACTION_INPUT_CHARS} chars")

    if provider is None or not provider.is_configured():
        problem = provider.config_problem if provider else "LLM_PROVIDER is none"
        log.warning("claim extraction refused: LLM not configured (%s)", problem)
        return _failure(
            503,
            SystemErrorInfo(
                code=SystemErrorCode.LLM_NOT_CONFIGURED,
                stage=PipelineStage.CLAIM_EXTRACTION,
                message=_PUBLIC_MESSAGE[SystemErrorCode.LLM_NOT_CONFIGURED],
                retryable=False,
            ),
        )

    extractor = LlmClaimExtractor(provider)
    try:
        result = await extractor.extract(
            ExtractionInput(mode=CheckMode.FULL_CONTENT, text=body.text)
        )
    except MizanError as exc:
        info = exc.to_info()
        log.warning("claim extraction failed: code=%s detail=%s", info.code.value, info.message)
        public = info.model_copy(
            update={
                "message": _PUBLIC_MESSAGE.get(info.code, "Claim extraction failed"),
                "stage": PipelineStage.CLAIM_EXTRACTION,
            }
        )
        return _failure(_HTTP_FOR_CODE.get(info.code, 502), public)
    except Exception as exc:  # noqa: BLE001 - technical failure, never "no claims"
        log.error(
            "unexpected claim extraction error:\n%s",
            format_exception_safely(exc, _secrets(settings)),
        )
        return _failure(
            500,
            SystemErrorInfo(
                code=SystemErrorCode.INTERNAL_ERROR,
                stage=PipelineStage.CLAIM_EXTRACTION,
                message="Claim extraction failed",
            ),
        )

    return ExtractResponse(
        claims=[
            ExtractedClaimOut(
                claim_id=c.claim_id,
                original_text=c.original_text,
                extracted_claim_text=c.extracted_claim_text or "",
                extraction_status=c.extraction_status or ExtractionStatus.CLEAR,
                provided_evidence=(
                    ProvidedEvidenceOut(
                        provided_evidence_type=c.provided_evidence.provided_evidence_type.value,
                        provided_evidence_text=c.provided_evidence.provided_evidence_text,
                    )
                    if c.provided_evidence
                    else None
                ),
                provided_reference=c.provided_reference,
                user_confirmation_status=c.user_confirmation_status,
            )
            for c in result.claims
        ],
        discarded_ungrounded_count=result.discarded_ungrounded_count,
    )


# --- confirmation gate -----------------------------------------------------------


def _to_domain_claim(c: ReviewedClaimIn) -> Claim:
    text = c.text
    if c.origin == "manual":
        status = UserConfirmationStatus.CONFIRMED
        extracted = None
        original = text
    else:
        extracted = c.extracted_claim_text
        status = (
            UserConfirmationStatus.CONFIRMED
            if extracted is not None and text == extracted
            else UserConfirmationStatus.EDITED
        )
        original = c.original_text
    return Claim(
        claim_id=c.claim_id,
        original_text=original,
        extracted_claim_text=extracted,
        confirmed_claim_text=text,
        extraction_status=c.extraction_status if c.origin == "extracted" else None,
        provided_evidence=c.provided_evidence,
        provided_reference=c.provided_reference,
        user_confirmation_status=status,
        selected_for_verification=c.selected,
    )


@router.post(
    "/confirm",
    response_model=ConfirmResponse,
    responses={422: {"model": InputErrorResponse}},
)
async def confirm_claims(body: ConfirmRequest):
    if not body.explicit_user_confirmation:
        return _input_error(422, "confirmation_required", "explicit user confirmation is required")
    selected = [c for c in body.claims if c.selected]
    if not selected:
        return _input_error(422, "no_claims_selected", "select at least one claim")
    if any(not c.text.strip() for c in selected):
        return _input_error(422, "empty_claim_text", "a selected claim has no text")
    ids = [c.claim_id for c in body.claims]
    if len(ids) != len(set(ids)):
        return _input_error(422, "duplicate_claim_id", "claim ids must be unique")
    try:
        confirmed = select_confirmed_claims([_to_domain_claim(c) for c in body.claims])
    except ClaimNotConfirmedError as exc:  # pragma: no cover - guarded above
        return _input_error(422, "not_confirmed", str(exc))
    log.info("claims confirmed: received=%d confirmed=%d", len(body.claims), len(confirmed))
    return ConfirmResponse(confirmed_claims=confirmed)
