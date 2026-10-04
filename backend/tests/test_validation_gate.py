"""Final Validation Gate: integrity failures RETRY (fail closed), never an evidentiary status."""

from __future__ import annotations

import pytest

from app.domain.claim import ConfirmedClaim
from app.domain.enums import (
    ClaimType,
    RetrievalMatchBasis,
    RetryReason,
    UserConfirmationStatus,
    ValidationCheck,
    ValidationOutcome,
    VerificationStatus,
)
from app.domain.enums import ComponentOutcome as O
from app.pipeline.analysis import (
    DeterministicEvidenceAnalyzer,
    DeterministicStatusDeterminer,
    component_outcome,
    status_from_outcomes,
)
from app.pipeline.classification import LlmClaimClassifier
from app.pipeline.gate import TrustedValidationGate
from app.pipeline.retrieval import TrustedSourceRetriever
from app.pipeline.routing import DeterministicSourceRouter
from app.pipeline.verification import TrustedEvidenceVerifier
from tests.test_task5a_pipeline import registry
from tests.test_verification_engine import ScriptedLLM, cls, handler

TEXT = "قال تعالى في سورة البقرة: «إن الصفا والمروة من شعائر الله»"


async def stages(text=TEXT):
    reg = registry(handler=handler)
    llm = ScriptedLLM(cls(ClaimType.QURAN))
    claim = await LlmClaimClassifier(llm).classify(
        ConfirmedClaim(
            claim_id="c1",
            confirmed_claim_text=text,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED,
        )
    )
    plan = await DeterministicSourceRouter(reg).route(claim)
    retrieval = await TrustedSourceRetriever(reg).retrieve(claim, plan)
    findings = await TrustedEvidenceVerifier(reg, llm).verify(claim, retrieval.candidates)
    analysis = await DeterministicEvidenceAnalyzer().analyze(claim, findings)
    det = await DeterministicStatusDeterminer().determine(claim, analysis, retrieval)
    return claim, retrieval, analysis, det


async def gate(claim, retrieval, analysis, det):
    return await TrustedValidationGate().validate(
        claim, retrieval, analysis, det, retry_count=0, retries_remaining=2
    )


async def test_clean_verification_passes_all_seven_checks():
    claim, retrieval, analysis, det = await stages()
    v = await gate(claim, retrieval, analysis, det)
    assert v.outcome == ValidationOutcome.PASS and {c.check for c in v.checks} == set(
        ValidationCheck
    )


def failed(v):
    return {c.check for c in v.checks if not c.passed}


async def test_status_recomputation_mismatch_is_integrity_failure():
    claim, retrieval, analysis, det = await stages()
    v = await gate(
        claim,
        retrieval,
        analysis,
        det.model_copy(update={"status": VerificationStatus.CONTRADICTED}),
    )
    assert v.outcome == ValidationOutcome.RETRY and v.retry_reason == RetryReason.INTEGRITY_FAILURE
    assert ValidationCheck.STATUS_MATCHES_EVIDENCE in failed(v)


async def test_tampered_evidence_text_breaks_traceability():
    claim, retrieval, analysis, det = await stages()
    c0 = retrieval.candidates[0]
    tampered = c0.model_copy(
        update={"evidence": c0.evidence.model_copy(update={"text": c0.evidence.text + " زيادة"})}
    )
    retrieval = retrieval.model_copy(update={"candidates": [tampered, *retrieval.candidates[1:]]})
    v = await gate(claim, retrieval, analysis, det)
    assert v.outcome == ValidationOutcome.RETRY and ValidationCheck.EVIDENCE_TRACEABLE in failed(v)


async def test_keyword_basis_evidence_cannot_be_counted():
    claim, retrieval, analysis, det = await stages()
    weak = [
        c.model_copy(
            update={
                "retrieval": c.retrieval.model_copy(
                    update={"match_basis": RetrievalMatchBasis.KEYWORD}
                )
            }
        )
        for c in retrieval.candidates
    ]
    v = await gate(claim, retrieval.model_copy(update={"candidates": weak}), analysis, det)
    assert (
        v.outcome == ValidationOutcome.RETRY
        and ValidationCheck.SOURCE_APPROVED_AND_QUALIFIED in failed(v)
    )


async def test_span_not_in_evidence_is_integrity_failure():
    claim, retrieval, analysis, det = await stages()
    a0 = analysis.assessments[0].model_copy(update={"evidence_span": "كلمات ليست في الآية إطلاقا"})
    analysis = analysis.model_copy(update={"assessments": [a0, *analysis.assessments[1:]]})
    v = await gate(claim, retrieval, analysis, det)
    assert (
        v.outcome == ValidationOutcome.RETRY
        and ValidationCheck.REFERENCES_FROM_VERIFIED_METADATA in failed(v)
    )


async def test_weak_retrieval_with_no_evidence_abstains_to_the_same_status():
    claim, retrieval, analysis, det = await stages("في القرآن أن الحي القيوم لا يأخذه نوم ولا نعاس")
    v = await gate(claim, retrieval, analysis, det)
    assert (
        v.outcome == ValidationOutcome.ABSTAIN
        and v.abstained_to == det.status == VerificationStatus.NO_EVIDENCE_FOUND
    )


@pytest.mark.parametrize(
    "outcomes,status",
    [
        ([O.SUPPORTED, O.CONTRADICTED], VerificationStatus.CONTRADICTED),
        ([O.SUPPORTED, O.CONFLICTING], VerificationStatus.CONFLICTING_EVIDENCE),
        ([O.SUPPORTED, O.SUPPORTED], VerificationStatus.SUPPORTED),
        ([O.SUPPORTED, O.NOT_ESTABLISHED], VerificationStatus.PARTIALLY_SUPPORTED),
        ([O.PARTIALLY_SUPPORTED], VerificationStatus.PARTIALLY_SUPPORTED),
        ([O.INSUFFICIENT, O.NOT_ESTABLISHED], VerificationStatus.INSUFFICIENT_EVIDENCE),
        ([O.NOT_ESTABLISHED], VerificationStatus.NO_EVIDENCE_FOUND),
        ([], VerificationStatus.NO_EVIDENCE_FOUND),
    ],
)
def test_status_rule_table(outcomes, status):
    assert status_from_outcomes(outcomes) == status


def test_component_rule_needs_no_quantity():
    from app.domain.enums import EvidenceRelationship as R
    from app.domain.verification import EvidenceAssessment

    def a(rel, eid):
        return EvidenceAssessment(
            evidence_id=eid,
            relationship=rel,
            rationale="r",
            evidence_span=None if rel == R.INSUFFICIENT else "x y z",
        )

    assert component_outcome([a(R.INSUFFICIENT, f"e{i}") for i in range(5)]) == O.INSUFFICIENT
    assert component_outcome([a(R.SUPPORTS, "e1"), a(R.CONTRADICTS, "e2")]) == O.CONFLICTING
