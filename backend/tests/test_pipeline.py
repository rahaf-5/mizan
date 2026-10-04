from __future__ import annotations

import pytest

from app.domain.claim import Claim, ClassifiedClaim
from app.domain.enums import (
    ClaimType,
    OutOfScopeReason,
    PipelineStage,
    RetryReason,
    SystemErrorCode,
    UserConfirmationStatus,
    ValidationOutcome,
    VerificationStatus,
)
from app.domain.errors import ClaimNotConfirmedError, SourceUnavailableError
from app.domain.results import OutOfScopeOutcome, SystemErrorOutcome, VerificationOutcome
from app.domain.retrieval import RetrievalResult
from app.domain.routing import SourceRoute, SourceRoutingPlan
from app.domain.trusted_sources import TrustedSourceId
from app.domain.validation import FinalValidationResult
from app.domain.verification import AnalysisResult, StatusDetermination
from app.pipeline import contracts, stubs
from app.pipeline.orchestrator import PipelineStages, VerificationPipeline, build_stub_pipeline


def confirmed_claim(**kw) -> Claim:
    base = dict(
        original_text="نص",
        confirmed_claim_text="ادعاء",
        user_confirmation_status=UserConfirmationStatus.CONFIRMED,
    )
    base.update(kw)
    return Claim(**base)


def test_stubs_satisfy_stage_contracts():
    pairs = [
        (stubs.StubClaimExtractor(), contracts.ClaimExtractor),
        (stubs.StubClaimClassifier(), contracts.ClaimClassifier),
        (stubs.StubSourceRouter(), contracts.SourceRouter),
        (stubs.StubHybridRetriever(), contracts.HybridRetriever),
        (stubs.StubEvidenceVerifier(), contracts.EvidenceVerifier),
        (stubs.StubEvidenceAnalyzer(), contracts.EvidenceAnalyzer),
        (stubs.StubStatusDeterminer(), contracts.StatusDeterminer),
        (stubs.StubFinalValidationGate(), contracts.FinalValidationGate),
        (stubs.StubResultBuilder(), contracts.ResultBuilder),
    ]
    for impl, proto in pairs:
        assert isinstance(impl, proto)


async def test_stub_pipeline_reports_system_error_not_evidence_status():
    result = await build_stub_pipeline(max_retries=2).run([confirmed_claim()])
    [outcome] = result.outcomes
    assert isinstance(outcome, SystemErrorOutcome)
    assert outcome.error.code == SystemErrorCode.STAGE_NOT_IMPLEMENTED
    assert outcome.error.stage == PipelineStage.CLAIM_CLASSIFICATION


async def test_pipeline_refuses_unconfirmed_claims():
    with pytest.raises(ClaimNotConfirmedError):
        await build_stub_pipeline(max_retries=2).run([Claim(original_text="نص")])


async def test_pipeline_skips_deselected_claims():
    result = await build_stub_pipeline(max_retries=2).run(
        [Claim(original_text="نص", selected_for_verification=False)]
    )
    assert result.outcomes == []


def test_negative_retry_limit_rejected():
    with pytest.raises(ValueError):
        build_stub_pipeline(max_retries=-1)


# --- Orchestration with fake stages (no verification logic invented) ---------

PLAN = SourceRoutingPlan(
    claim_id="x",
    routes=[SourceRoute(required_claim_type=ClaimType.QURAN, sources=[TrustedSourceId.QURAN])],
)


class FakeClassifier:
    def __init__(self, out_of_scope=False):
        self.out_of_scope = out_of_scope

    async def classify(self, claim):
        if self.out_of_scope:
            return OutOfScopeOutcome(
                claim_id=claim.claim_id, reason=OutOfScopeReason.UNSUPPORTED_CLAIM_CATEGORY
            )
        return ClassifiedClaim(
            **claim.model_dump(exclude={"claim_type"}), claim_type=ClaimType.QURAN
        )


class FakeRouter:
    async def route(self, claim):
        return PLAN


class CountingRetriever:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    async def retrieve(self, claim, plan, *, attempt=0):
        self.calls += 1
        if self.fail:
            raise SourceUnavailableError("source down")
        return RetrievalResult(claim_id=claim.claim_id)


class FakeVerifier:
    async def verify(self, claim, candidates):
        return []


class FakeAnalyzer:
    async def analyze(self, claim, assessments):
        return AnalysisResult(claim_id=claim.claim_id)


class FakeStatus:
    async def determine(self, claim, analysis, retrieval):
        return StatusDetermination(
            claim_id=claim.claim_id, status=VerificationStatus.NO_EVIDENCE_FOUND
        )


class AlwaysRetryGate:
    def __init__(self):
        self.remaining_seen = []

    async def validate(
        self, claim, retrieval, analysis, determination, *, retry_count, retries_remaining
    ):
        self.remaining_seen.append(retries_remaining)
        return FinalValidationResult(
            claim_id=claim.claim_id,
            outcome=ValidationOutcome.RETRY,
            retry_count=retry_count,
            retry_reason=RetryReason.WEAK_RETRIEVAL,
        )


def make_pipeline(max_retries=2, classifier=None, retriever=None, gate=None, builder=None):
    return VerificationPipeline(
        PipelineStages(
            classifier=classifier or FakeClassifier(),
            router=FakeRouter(),
            retriever=retriever or CountingRetriever(),
            verifier=FakeVerifier(),
            analyzer=FakeAnalyzer(),
            status=FakeStatus(),
            gate=gate or AlwaysRetryGate(),
            builder=builder or stubs.StubResultBuilder(),
        ),
        max_retries=max_retries,
    )


@pytest.mark.parametrize("limit", [0, 1, 3])
async def test_retries_are_bounded_by_configuration(limit):
    retriever = CountingRetriever()
    result = await make_pipeline(max_retries=limit, retriever=retriever).run([confirmed_claim()])
    assert retriever.calls == limit + 1
    [outcome] = result.outcomes
    assert isinstance(outcome, SystemErrorOutcome)
    assert outcome.error.code == SystemErrorCode.VERIFICATION_INCOMPLETE


async def test_source_failure_becomes_system_error_not_insufficient_evidence():
    result = await make_pipeline(retriever=CountingRetriever(fail=True)).run([confirmed_claim()])
    [outcome] = result.outcomes
    assert isinstance(outcome, SystemErrorOutcome)
    assert outcome.error.code == SystemErrorCode.SOURCE_UNAVAILABLE


async def test_out_of_scope_passes_through_as_its_own_outcome():
    result = await make_pipeline(classifier=FakeClassifier(out_of_scope=True)).run(
        [confirmed_claim()]
    )
    [outcome] = result.outcomes
    assert isinstance(outcome, OutOfScopeOutcome)
    assert outcome.kind == "out_of_scope"


async def test_gate_is_told_remaining_retry_budget():
    gate = AlwaysRetryGate()
    await make_pipeline(max_retries=2, gate=gate).run([confirmed_claim()])
    assert gate.remaining_seen == [2, 1, 0]


class AbstainWhenBudgetExhaustedGate:
    """Evidentiary limitation: retry while budget remains, then abstain (locked rule)."""

    async def validate(
        self, claim, retrieval, analysis, determination, *, retry_count, retries_remaining
    ):
        if retries_remaining > 0:
            return FinalValidationResult(
                claim_id=claim.claim_id,
                outcome=ValidationOutcome.RETRY,
                retry_count=retry_count,
                retry_reason=RetryReason.WEAK_RETRIEVAL,
            )
        return FinalValidationResult(
            claim_id=claim.claim_id,
            outcome=ValidationOutcome.ABSTAIN,
            retry_count=retry_count,
            abstained_to=VerificationStatus.NO_EVIDENCE_FOUND,
        )


class PassThroughBuilder:
    async def build(self, claim, retrieval, analysis, determination, validation):
        return VerificationOutcome(
            claim_id=claim.claim_id,
            confirmed_claim_text=claim.confirmed_claim_text,
            status=determination.status,
            analysis=analysis,
            validation=validation,
        )


async def test_evidentiary_exhaustion_abstains_to_status_not_system_error():
    result = await make_pipeline(
        max_retries=1, gate=AbstainWhenBudgetExhaustedGate(), builder=PassThroughBuilder()
    ).run([confirmed_claim()])
    [outcome] = result.outcomes
    assert isinstance(outcome, VerificationOutcome)
    assert outcome.status == VerificationStatus.NO_EVIDENCE_FOUND
    assert outcome.validation.outcome == ValidationOutcome.ABSTAIN
