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
from app.domain.errors import SystemErrorInfo
from app.domain.inputs import MAX_REVIEW_CLAIMS
from app.domain.results import FinalUserResult, SystemErrorOutcome
from app.llm.base import LLMProvider
from app.pipeline.factory import build_verification_pipeline
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
        return JSONResponse(
            status_code=422,
            content={
                "kind": "input_error",
                "code": "duplicate_claim_id",
                "message": "claim ids must be unique",
            },
        )
    if provider is None or not provider.is_configured():
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
    pipeline = build_verification_pipeline(settings, provider, registry)
    result = await pipeline.run_confirmed(body.claims)
    return _public(result).model_dump(mode="json")
