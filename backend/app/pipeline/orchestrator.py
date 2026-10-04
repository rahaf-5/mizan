"""Pipeline orchestrator skeleton.

Wires the stage contracts in the approved order. Implemented behaviour is
limited to rules stated in the spec:
  * only selected, user-confirmed claims enter verification (spec §2);
  * Retry is bounded by configuration (spec §10); the limit is injected, not hardcoded;
  * technical failures become SystemErrorOutcome, never an evidence status (spec §17);
  * Out of Scope from classification/routing is passed through as its own outcome.

PROVISIONAL (needs product confirmation, see README "Open decisions"):
when the retry budget is exhausted and the gate still asks to retry, the claim
ends as SystemErrorOutcome(code=verification_incomplete) — "verification could
not be completed, allow retry" (spec §17) — rather than any evidence status.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.claim import Claim, ClassifiedClaim, select_confirmed_claims
from app.domain.enums import PipelineStage, SystemErrorCode, ValidationOutcome
from app.domain.errors import MizanError, SystemErrorInfo
from app.domain.results import ClaimOutcome, FinalUserResult, OutOfScopeOutcome, SystemErrorOutcome
from app.pipeline.contracts import (
    ClaimClassifier,
    EvidenceAnalyzer,
    EvidenceVerifier,
    FinalValidationGate,
    HybridRetriever,
    ResultBuilder,
    SourceRouter,
    StatusDeterminer,
)


@dataclass
class PipelineStages:
    classifier: ClaimClassifier
    router: SourceRouter
    retriever: HybridRetriever
    verifier: EvidenceVerifier
    analyzer: EvidenceAnalyzer
    status: StatusDeterminer
    gate: FinalValidationGate
    builder: ResultBuilder


class VerificationPipeline:
    """Runs confirmed claims from Claim Classification to Final User Result."""

    def __init__(self, stages: PipelineStages, *, max_retries: int) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self._s = stages
        self._max_retries = max_retries

    async def run(self, claims: list[Claim]) -> FinalUserResult:
        confirmed = select_confirmed_claims(claims)  # raises if a selected claim is unconfirmed
        outcomes: list[ClaimOutcome] = []
        for claim in confirmed:
            outcomes.append(await self._run_one_safely(claim))
        return FinalUserResult(run_id=str(uuid.uuid4()), outcomes=outcomes)

    async def _run_one_safely(self, claim) -> ClaimOutcome:  # type: ignore[no-untyped-def]
        current_stage = PipelineStage.CLAIM_CLASSIFICATION
        try:
            classified = await self._s.classifier.classify(claim)
            if isinstance(classified, OutOfScopeOutcome):
                return classified
            current_stage = PipelineStage.SOURCE_ROUTING
            plan = await self._s.router.route(classified)
            if isinstance(plan, OutOfScopeOutcome):
                return plan
            return await self._verify_with_retries(classified, plan)
        except MizanError as exc:
            info = exc.to_info()
            if info.stage is None:
                info = info.model_copy(update={"stage": current_stage})
            return SystemErrorOutcome(claim_id=claim.claim_id, error=info)
        except Exception as exc:  # noqa: BLE001 - technical failure, never an evidence verdict
            return SystemErrorOutcome(
                claim_id=claim.claim_id,
                error=SystemErrorInfo(
                    code=SystemErrorCode.INTERNAL_ERROR,
                    stage=current_stage,
                    message=f"{type(exc).__name__}: {exc}",
                ),
            )

    async def _verify_with_retries(self, claim: ClassifiedClaim, plan) -> ClaimOutcome:  # type: ignore[no-untyped-def]
        retry_count = 0
        while True:
            retrieval = await self._s.retriever.retrieve(claim, plan, attempt=retry_count)
            assessments = await self._s.verifier.verify(claim, retrieval.candidates)
            analysis = await self._s.analyzer.analyze(claim, assessments)
            determination = await self._s.status.determine(claim, analysis, retrieval)
            validation = await self._s.gate.validate(
                claim, retrieval, analysis, determination, retry_count=retry_count
            )
            if validation.outcome != ValidationOutcome.RETRY:
                return await self._s.builder.build(
                    claim, retrieval, analysis, determination, validation
                )
            if retry_count >= self._max_retries:
                return SystemErrorOutcome(
                    claim_id=claim.claim_id,
                    error=SystemErrorInfo(
                        code=SystemErrorCode.VERIFICATION_INCOMPLETE,
                        stage=PipelineStage.FINAL_VALIDATION_GATE,
                        message="verification could not be completed within the retry limit",
                        retryable=True,
                    ),
                )
            retry_count += 1


def build_stub_pipeline(max_retries: int) -> VerificationPipeline:
    """Pipeline wired with placeholder stages (Task 1)."""
    from app.pipeline import stubs

    return VerificationPipeline(
        PipelineStages(
            classifier=stubs.StubClaimClassifier(),
            router=stubs.StubSourceRouter(),
            retriever=stubs.StubHybridRetriever(),
            verifier=stubs.StubEvidenceVerifier(),
            analyzer=stubs.StubEvidenceAnalyzer(),
            status=stubs.StubStatusDeterminer(),
            gate=stubs.StubFinalValidationGate(),
            builder=stubs.StubResultBuilder(),
        ),
        max_retries=max_retries,
    )
