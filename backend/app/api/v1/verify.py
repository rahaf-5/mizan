"""POST /api/v1/verify — confirmed claims in, verification results out (Task 5b, backend only).

Only claims that already passed the confirmation gate (`ConfirmedClaim`) are accepted. Each
claim ends in exactly one outcome: verification (one of the six statuses), out_of_scope,
required_source_unavailable (explicit abstention) or system_error (technical; never a status).
Provider internals are logged server-side; per-claim system-error messages are generic.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.claims import FailureResponse, get_llm_provider
from app.config import Settings, get_settings
from app.core_logging import get_logger
from app.domain.claim import ConfirmedClaim
from app.domain.enums import PipelineStage, SystemErrorCode
from app.domain.errors import MizanError, SystemErrorInfo
from app.domain.inputs import MAX_CLAIM_CHARS, MAX_REVIEW_CLAIMS
from app.domain.results import FinalUserResult, SystemErrorOutcome, VerificationOutcome
from app.llm.base import LLMProvider
from app.pipeline.alternative_wording import AlternativeWordingService, is_eligible
from app.pipeline.factory import build_verification_pipeline
from app.pipeline.result_store import RESULTS
from app.sources.dorar import DorarAdapter
from app.sources.quranpedia import QuranpediaAdapter
from app.sources.registry import AdapterRegistry

router = APIRouter(tags=["verification"])
log = get_logger("api.verify")

_PUBLIC = {
    SystemErrorCode.SOURCE_UNAVAILABLE: "An approved source is temporarily unavailable",
    SystemErrorCode.VERIFICATION_INCOMPLETE: "Verification could not be completed reliably",
    SystemErrorCode.LLM_RATE_LIMITED: "The analysis service is busy; try again later",
    SystemErrorCode.LLM_TIMEOUT: "The analysis service timed out",
}
_GENERIC = "Verification could not be completed"


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[ConfirmedClaim] = Field(min_length=1, max_length=MAX_REVIEW_CLAIMS)


class AlternativeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=100)
    claim_id: str = Field(min_length=1, max_length=100)


def _input_error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"kind": "input_error", "code": code, "message": message}
    )


def _not_configured() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=FailureResponse(
            error=SystemErrorInfo(
                code=SystemErrorCode.LLM_NOT_CONFIGURED,
                stage=PipelineStage.CLAIM_CLASSIFICATION,
                message="Verification analysis service is not configured",
                retryable=False,
            )
        ).model_dump(mode="json"),
    )


@lru_cache(maxsize=4)
def _registry(enabled: bool, base_url: str | None, data_dir: str | None, timeout: int, dorar: bool):  # type: ignore[no-untyped-def]
    reg = AdapterRegistry()
    reg.register(
        QuranpediaAdapter(
            enabled=enabled,
            base_url=base_url,
            data_dir=Path(data_dir) if data_dir else None,
            timeout_seconds=timeout,
        )
    )
    reg.register(DorarAdapter(enabled=dorar))
    return reg


def get_registry(settings: Annotated[Settings, Depends(get_settings)]) -> AdapterRegistry:
    """One registry (and one loaded Mushaf 1 index) per configuration."""
    return _registry(
        settings.quranpedia_enabled,
        settings.quranpedia_base_url,
        settings.quran_data_dir,
        settings.source_request_timeout_seconds,
        settings.dorar_enabled,
    )


def _public(result: FinalUserResult) -> FinalUserResult:
    outcomes = []
    for o in result.outcomes:
        if isinstance(o, SystemErrorOutcome):
            log.warning(
                "verify: claim %s system error %s: %s",
                o.claim_id,
                o.error.code.value,
                o.error.message,
            )
            o = o.model_copy(
                update={
                    "error": o.error.model_copy(
                        update={"message": _PUBLIC.get(o.error.code, _GENERIC)}
                    )
                }
            )
        outcomes.append(o)
    return result.model_copy(update={"outcomes": outcomes})


@router.post("/verify")
async def verify_claims(
    body: VerifyRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    provider: Annotated[LLMProvider | None, Depends(get_llm_provider)],
    registry: Annotated[AdapterRegistry, Depends(get_registry)],
):
    ids = [c.claim_id for c in body.claims]
    if len(ids) != len(set(ids)):
        return _input_error(422, "duplicate_claim_id", "claim ids must be unique")
    if any(len(c.confirmed_claim_text) > MAX_CLAIM_CHARS for c in body.claims):
        return _input_error(413, "claim_too_long", f"maximum is {MAX_CLAIM_CHARS} chars")
    if provider is None or not provider.is_configured():
        return _not_configured()
    pipeline = build_verification_pipeline(settings, provider, registry)
    result = await pipeline.run_confirmed(body.claims)
    by_id = {c.claim_id: c for c in body.claims}
    for o in result.outcomes:
        if isinstance(o, VerificationOutcome):
            RESULTS.put(result.run_id, by_id[o.claim_id], o)
    return _public(result).model_dump(mode="json")


@router.post("/alternative-wording")
async def alternative_wording(
    body: AlternativeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    provider: Annotated[LLMProvider | None, Depends(get_llm_provider)],
    registry: Annotated[AdapterRegistry, Depends(get_registry)],
):
    """Spec §15: propose ONE wording from the server's own validated result, then re-verify it
    through the full pipeline. `verified` is true only if the re-verification is `supported`."""
    stored = RESULTS.get(body.run_id, body.claim_id)
    if stored is None:
        return _input_error(404, "result_not_found", "verify the claim again first")
    claim, outcome = stored
    if not is_eligible(outcome):
        return _input_error(422, "not_eligible", "alternative wording is not appropriate here")
    if provider is None or not provider.is_configured():
        return _not_configured()
    pipeline = build_verification_pipeline(settings, provider, registry)
    try:
        alt = await AlternativeWordingService(provider, pipeline).propose(claim, outcome)
    except MizanError as exc:
        log.warning("alternative wording failed: %s", exc.to_info().message)
        return JSONResponse(
            status_code=502,
            content=FailureResponse(
                error=SystemErrorInfo(
                    code=exc.code,
                    stage=PipelineStage.FINAL_USER_RESULT,
                    message="Alternative wording could not be generated",
                    retryable=exc.retryable,
                )
            ).model_dump(mode="json"),
        )
    alt_run = f"{body.run_id}:alt"
    if alt.outcome is not None and isinstance(alt.outcome, VerificationOutcome):
        RESULTS.put(
            alt_run,
            ConfirmedClaim(
                claim_id=alt.outcome.claim_id,
                confirmed_claim_text=alt.outcome.confirmed_claim_text,
                user_confirmation_status="confirmed",
            ),
            alt.outcome,
        )
    outcome_json = None
    if alt.outcome is not None:
        wrapped = _public(FinalUserResult(run_id=alt_run, outcomes=[alt.outcome]))
        outcome_json = wrapped.outcomes[0].model_dump(mode="json")
    return {
        "kind": "alternative_wording",
        "original_claim_id": body.claim_id,
        "run_id": alt_run,
        "proposed_text": alt.proposed_text,
        "verified": alt.verified,
        "outcome": outcome_json,
    }
