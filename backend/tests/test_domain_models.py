from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.claim import (
    Claim,
    ClassifiedClaim,
    ConfirmedClaim,
    ProvidedEvidence,
    confirm_for_verification,
    select_confirmed_claims,
)
from app.domain.enums import (
    AsbabRelationType,
    CheckMode,
    ClaimType,
    EvidenceRelationship,
    InputType,
    OutOfScopeReason,
    ProvidedEvidenceType,
    RetrievalAttemptStatus,
    RetrievalMethod,
    RetryReason,
    SourceType,
    SystemErrorCode,
    UserConfirmationStatus,
    ValidationCheck,
    ValidationOutcome,
    VerificationStatus,
)
from app.domain.errors import ClaimNotConfirmedError, SystemErrorInfo
from app.domain.evidence import AsbabNuzulMetadata, Evidence, TafsirMetadata
from app.domain.inputs import ExtractionInput
from app.domain.results import (
    FinalUserResult,
    OutOfScopeOutcome,
    SystemErrorOutcome,
    VerificationOutcome,
)
from app.domain.retrieval import RetrievalAttempt, RetrievalResult
from app.domain.routing import SourceRoute, SourceRoutingPlan
from app.domain.trusted_sources import Provider, TrustedSourceId
from app.domain.validation import FinalValidationResult, ValidationCheckResult
from app.domain.verification import (
    AnalysisResult,
    ComponentFinding,
    EvidenceAssessment,
)
from tests.conftest import make_candidate, make_hadith_metadata, make_quran_evidence

# --- Claim confirmation gate ------------------------------------------------


def _claim(**kw) -> Claim:
    base = dict(original_text="نص", extracted_claim_text="ادعاء", confirmed_claim_text="ادعاء")
    base.update(kw)
    return Claim(**base)


def test_new_claim_defaults_pending_selected_unclassified():
    c = Claim(original_text="نص")
    assert c.user_confirmation_status == UserConfirmationStatus.PENDING
    assert c.selected_for_verification is True
    assert c.claim_type is None


def test_pending_claim_cannot_be_confirmed_for_verification():
    with pytest.raises(ClaimNotConfirmedError):
        confirm_for_verification(_claim())


@pytest.mark.parametrize(
    "status", [UserConfirmationStatus.CONFIRMED, UserConfirmationStatus.EDITED]
)
def test_confirmed_and_edited_pass_gate(status):
    cc = confirm_for_verification(_claim(user_confirmation_status=status))
    assert isinstance(cc, ConfirmedClaim)
    assert cc.confirmed_claim_text == "ادعاء"


def test_gate_requires_confirmed_text():
    with pytest.raises(ClaimNotConfirmedError):
        confirm_for_verification(
            _claim(
                confirmed_claim_text="  ", user_confirmation_status=UserConfirmationStatus.CONFIRMED
            )
        )


def test_deselected_claim_is_not_verified():
    deselected = _claim(
        user_confirmation_status=UserConfirmationStatus.CONFIRMED, selected_for_verification=False
    )
    with pytest.raises(ClaimNotConfirmedError):
        confirm_for_verification(deselected)
    pending_but_deselected = _claim(selected_for_verification=False)
    assert select_confirmed_claims([deselected, pending_but_deselected]) == []


def test_selected_unconfirmed_claim_blocks_run():
    ok = _claim(user_confirmation_status=UserConfirmationStatus.CONFIRMED)
    with pytest.raises(ClaimNotConfirmedError):
        select_confirmed_claims([ok, _claim()])


def test_confirmed_claim_cannot_be_constructed_as_pending():
    with pytest.raises(ValidationError):
        ConfirmedClaim(
            claim_id="c",
            confirmed_claim_text="x",
            user_confirmation_status=UserConfirmationStatus.PENDING,
        )


def test_classified_claim_requires_type():
    with pytest.raises(ValidationError):
        ClassifiedClaim(
            claim_id="c",
            confirmed_claim_text="x",
            user_confirmation_status=UserConfirmationStatus.CONFIRMED,
        )
    ok = ClassifiedClaim(
        claim_id="c",
        confirmed_claim_text="x",
        claim_type=ClaimType.HADITH,
        user_confirmation_status=UserConfirmationStatus.CONFIRMED,
    )
    assert ok.claim_type == ClaimType.HADITH


def test_provided_reference_kept_separate_from_verified_reference():
    c = _claim(
        provided_reference="كما كتبه المستخدم",
        provided_evidence=ProvidedEvidence(
            provided_evidence_type=ProvidedEvidenceType.HADITH, provided_evidence_text="نص"
        ),
    )
    assert c.provided_reference == "كما كتبه المستخدم"
    assert c.verified_reference is None


# --- Input / OCR rule -------------------------------------------------------


def test_unreviewed_ocr_text_cannot_enter_extraction():
    with pytest.raises(ValidationError):
        ExtractionInput(mode=CheckMode.FULL_CONTENT, input_type=InputType.IMAGE, text="نص")
    ok = ExtractionInput(
        mode=CheckMode.FULL_CONTENT,
        input_type=InputType.IMAGE,
        text="نص",
        ocr_text_reviewed_by_user=True,
    )
    assert ok.ocr_text_reviewed_by_user


def test_quick_check_is_text_only():
    with pytest.raises(ValidationError):
        ExtractionInput(
            mode=CheckMode.QUICK_CHECK,
            input_type=InputType.IMAGE,
            text="نص",
            ocr_text_reviewed_by_user=True,
        )


# --- Evidence schema ---------------------------------------------------------


def test_valid_evidence_is_traceable():
    ev = make_quran_evidence()
    assert ev.source_name and ev.provider and ev.source_record_id and ev.reference


@pytest.mark.parametrize("field", ["reference", "source_record_id", "source_name", "text"])
def test_evidence_without_traceability_rejected(field):
    with pytest.raises(ValidationError):
        make_quran_evidence(**{field: ""})


def test_evidence_provider_must_match_allowlist():
    with pytest.raises(ValidationError):
        make_quran_evidence(provider=Provider.DORAR_AL_SUNNIYAH)


def test_evidence_metadata_must_match_source_type():
    with pytest.raises(ValidationError):
        make_quran_evidence(
            source_type=SourceType.HADITH,
            trusted_source_id=TrustedSourceId.DORAR_HADITH,
            provider=Provider.DORAR_AL_SUNNIYAH,
        )


def test_unknown_source_rejected():
    with pytest.raises(ValidationError):
        make_quran_evidence(trusted_source_id="some_website")


def test_hadith_grading_must_be_attributed():
    with pytest.raises(ValidationError):
        make_hadith_metadata(grading="درجة تجريبية")
    md = make_hadith_metadata(grading="درجة تجريبية", muhaddith="محدث تجريبي")
    assert md.muhaddith


def test_hadith_grading_optional_never_invented():
    assert make_hadith_metadata().grading is None


def test_tafsir_and_asbab_ranges():
    with pytest.raises(ValidationError):
        TafsirMetadata(
            tafsir_name="t",
            author="a",
            surah_number=2,
            surah_name_ar="s",
            ayah_start=5,
            ayah_end=4,
            chunk_id="c",
        )
    md = AsbabNuzulMetadata(
        asbab_source_name="s",
        author="a",
        surah_number=2,
        surah_name_ar="s",
        ayah_start=1,
        ayah_end=1,
        chunk_id="c",
        relation_type=AsbabRelationType.CONTEXTUAL,
    )
    assert md.relation_type == AsbabRelationType.CONTEXTUAL


def test_evidence_roundtrips_json():
    ev = make_quran_evidence()
    assert Evidence.model_validate_json(ev.model_dump_json()) == ev


# --- Retrieval ---------------------------------------------------------------


def _attempt(status, error=None):
    return RetrievalAttempt(
        source=TrustedSourceId.QURAN,
        method=RetrievalMethod.EXACT,
        query_text="q",
        status=status,
        error=error,
    )


def _err():
    return SystemErrorInfo(code=SystemErrorCode.SOURCE_UNAVAILABLE, message="down")


def test_failed_attempt_requires_error_and_vice_versa():
    with pytest.raises(ValidationError):
        _attempt(RetrievalAttemptStatus.FAILED)
    with pytest.raises(ValidationError):
        _attempt(RetrievalAttemptStatus.COMPLETED, _err())


def test_technical_failure_is_not_no_evidence_found():
    r = RetrievalResult(claim_id="c", attempts=[_attempt(RetrievalAttemptStatus.FAILED, _err())])
    assert r.all_attempts_failed
    assert not r.no_candidates_after_completed_search


def test_completed_search_without_candidates_is_retrieval_outcome():
    r = RetrievalResult(claim_id="c", attempts=[_attempt(RetrievalAttemptStatus.COMPLETED)])
    assert r.no_candidates_after_completed_search
    assert not r.all_attempts_failed


def test_candidate_searched_source_must_match_evidence():
    from app.domain.retrieval import CandidateEvidence, RetrievalMetadata

    with pytest.raises(ValidationError):
        CandidateEvidence(
            evidence=make_quran_evidence(),
            retrieval=RetrievalMetadata(
                retrieval_method=RetrievalMethod.SEMANTIC,
                retrieval_rank=1,
                searched_source=TrustedSourceId.TAFSIR_IBN_KATHIR,
            ),
        )


# --- Routing -----------------------------------------------------------------


def test_route_rejects_unqualified_source():
    with pytest.raises(ValidationError):
        SourceRoute(required_claim_type=ClaimType.ASBAB_NUZUL, sources=[TrustedSourceId.QURAN])


def test_cross_source_requires_signal():
    with pytest.raises(ValidationError):
        SourceRoute(
            required_claim_type=ClaimType.TAFSIR,
            sources=[TrustedSourceId.TAFSIR_IBN_KATHIR],
            is_cross_source_check=True,
        )


def test_composite_plan():
    plan = SourceRoutingPlan(
        claim_id="c",
        routes=[
            SourceRoute(
                component_text="a",
                required_claim_type=ClaimType.QURAN,
                sources=[TrustedSourceId.QURAN],
            ),
            SourceRoute(
                component_text="b",
                required_claim_type=ClaimType.ASBAB_NUZUL,
                sources=[TrustedSourceId.ASBAB_AL_NUZUL_AL_WAHIDI],
            ),
        ],
    )
    assert plan.is_composite
    single = SourceRoutingPlan(
        claim_id="c",
        routes=[
            SourceRoute(
                required_claim_type=ClaimType.TAFSIR,
                sources=[TrustedSourceId.TAFSIR_AL_MUYASSAR, TrustedSourceId.TAFSIR_IBN_KATHIR],
            )
        ],
    )
    assert not single.is_composite


# --- Verification / analysis -------------------------------------------------


def _assessment(eid="ev-q-1", rel=EvidenceRelationship.SUPPORTS, **kw):
    return EvidenceAssessment(evidence_id=eid, relationship=rel, rationale="مبني على الدليل", **kw)


def test_partial_support_requires_both_parts():
    with pytest.raises(ValidationError):
        _assessment(rel=EvidenceRelationship.PARTIALLY_SUPPORTS, supported_part="x")
    a = _assessment(
        rel=EvidenceRelationship.PARTIALLY_SUPPORTS, supported_part="x", unsupported_part="y"
    )
    assert a.unsupported_part == "y"


def test_analysis_cannot_create_new_evidence():
    with pytest.raises(ValidationError):
        AnalysisResult(
            claim_id="c",
            assessments=[_assessment()],
            supported_components=[ComponentFinding(component_text="x", evidence_ids=["invented"])],
        )


# --- Final validation --------------------------------------------------------


def _all_checks(passed=True):
    return [ValidationCheckResult(check=c, passed=passed) for c in ValidationCheck]


def test_pass_requires_all_seven_checks_passed():
    FinalValidationResult(claim_id="c", outcome=ValidationOutcome.PASS, checks=_all_checks())
    with pytest.raises(ValidationError):
        FinalValidationResult(
            claim_id="c", outcome=ValidationOutcome.PASS, checks=_all_checks()[:-1]
        )
    with pytest.raises(ValidationError):
        FinalValidationResult(
            claim_id="c", outcome=ValidationOutcome.PASS, checks=_all_checks(passed=False)
        )


def test_retry_requires_reason_and_abstain_requires_mapping():
    with pytest.raises(ValidationError):
        FinalValidationResult(claim_id="c", outcome=ValidationOutcome.RETRY)
    FinalValidationResult(
        claim_id="c", outcome=ValidationOutcome.RETRY, retry_reason=RetryReason.WEAK_RETRIEVAL
    )
    with pytest.raises(ValidationError):
        FinalValidationResult(claim_id="c", outcome=ValidationOutcome.ABSTAIN)
    FinalValidationResult(
        claim_id="c",
        outcome=ValidationOutcome.ABSTAIN,
        abstained_to=VerificationStatus.INSUFFICIENT_EVIDENCE,
    )


# --- Outcomes ----------------------------------------------------------------


def _verification_outcome(**kw):
    ev = make_candidate().evidence
    base = dict(
        claim_id="c",
        confirmed_claim_text="ادعاء",
        status=VerificationStatus.SUPPORTED,
        analysis=AnalysisResult(claim_id="c", assessments=[_assessment(ev.evidence_id)]),
        validation=FinalValidationResult(
            claim_id="c", outcome=ValidationOutcome.PASS, checks=_all_checks()
        ),
        evidence=[ev],
    )
    base.update(kw)
    return VerificationOutcome(**base)


def test_verification_outcome_valid():
    assert _verification_outcome().status == VerificationStatus.SUPPORTED


def test_no_final_result_from_retry():
    with pytest.raises(ValidationError):
        _verification_outcome(
            validation=FinalValidationResult(
                claim_id="c",
                outcome=ValidationOutcome.RETRY,
                retry_reason=RetryReason.WEAK_RETRIEVAL,
            )
        )


def test_abstained_status_must_match_mapping():
    v = FinalValidationResult(
        claim_id="c",
        outcome=ValidationOutcome.ABSTAIN,
        abstained_to=VerificationStatus.INSUFFICIENT_EVIDENCE,
    )
    with pytest.raises(ValidationError):
        _verification_outcome(validation=v)
    ok = _verification_outcome(validation=v, status=VerificationStatus.INSUFFICIENT_EVIDENCE)
    assert ok.status == VerificationStatus.INSUFFICIENT_EVIDENCE


def test_assessed_evidence_must_be_included():
    with pytest.raises(ValidationError):
        _verification_outcome(evidence=[])


def test_three_outcome_kinds_are_distinct_and_serializable():
    result = FinalUserResult(
        run_id="r",
        outcomes=[
            _verification_outcome(),
            OutOfScopeOutcome(claim_id="c2", reason=OutOfScopeReason.OUTSIDE_SOURCE_COVERAGE),
            SystemErrorOutcome(claim_id="c3", error=_err()),
        ],
    )
    parsed = FinalUserResult.model_validate_json(result.model_dump_json())
    assert [o.kind for o in parsed.outcomes] == ["verification", "out_of_scope", "system_error"]
    assert not hasattr(parsed.outcomes[1], "status")
    assert not hasattr(parsed.outcomes[2], "status")
