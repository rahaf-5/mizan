"""Guards Mizan's approved states. If one of these fails, an approved product
contract changed — that requires explicit product approval (spec §19, §21)."""

from __future__ import annotations

from app.domain import contracts_export
from app.domain.enums import (
    PIPELINE_ORDER,
    AsbabRelationType,
    ClaimType,
    EvidenceRelationship,
    EvidenceStrengthSignal,
    ExtractionStatus,
    OutOfScopeReason,
    ResultGroup,
    RetrievalMethod,
    SourceType,
    SystemErrorCode,
    UserConfirmationStatus,
    ValidationCheck,
    ValidationOutcome,
    VerificationStatus,
)
from app.domain.trusted_sources import TRUSTED_SOURCES, Provider, TrustedSourceId


def values(enum) -> list[str]:
    return [m.value for m in enum]


def test_six_verification_statuses_exact_and_ordered():
    assert values(VerificationStatus) == [
        "supported",
        "partially_supported",
        "contradicted",
        "insufficient_evidence",
        "no_evidence_found",
        "conflicting_evidence",
    ]


def test_statuses_are_not_true_false_out_of_scope_or_error():
    forbidden = {"true", "false", "out_of_scope", "system_error", "error", "abstain", "unknown"}
    assert forbidden.isdisjoint(values(VerificationStatus))


def test_evidence_relationships_exact():
    assert values(EvidenceRelationship) == [
        "supports",
        "partially_supports",
        "contradicts",
        "insufficient",
    ]


def test_no_evidence_found_is_not_an_evidence_relationship():
    assert "no_evidence_found" not in values(EvidenceRelationship)


def test_out_of_scope_and_system_errors_are_separate_from_statuses():
    status_values = set(values(VerificationStatus))
    assert status_values.isdisjoint(values(OutOfScopeReason))
    assert status_values.isdisjoint(values(SystemErrorCode))
    assert "insufficient_evidence" not in values(SystemErrorCode)


def test_claim_enums_exact():
    assert values(ClaimType) == ["quran", "tafsir", "asbab_nuzul", "hadith"]
    assert values(SourceType) == ["quran", "tafsir", "asbab_nuzul", "hadith"]
    assert values(ExtractionStatus) == ["clear", "ambiguous", "incomplete"]
    assert values(UserConfirmationStatus) == ["pending", "confirmed", "edited"]


def test_retrieval_methods_and_asbab_relation():
    assert values(RetrievalMethod) == ["exact", "keyword", "semantic"]
    # `unspecified` approved 2026-10-04: never infer "direct cause".
    assert values(AsbabRelationType) == ["direct_sabab", "contextual", "unspecified"]


def test_validation_gate_contract():
    # Abstain is internal and is not a seventh status.
    assert values(ValidationOutcome) == ["pass", "retry", "abstain"]
    assert "abstain" not in values(VerificationStatus)
    assert len(ValidationCheck) == 7


def test_evidence_strength_has_signals_only():
    assert values(EvidenceStrengthSignal) == [
        "source_suitability",
        "directness",
        "completeness",
        "traceability",
        "match_quality",
        "agreement_or_conflict",
    ]


def test_mvp_input_is_text_only():
    from app.domain.enums import InputType

    assert values(InputType) == ["text"]


def test_no_ocr_error_codes_in_mvp():
    assert not [c for c in values(SystemErrorCode) if c.startswith("ocr")]


def test_four_result_groups():
    assert len(ResultGroup) == 4


def test_pipeline_order_matches_spec():
    assert [s.value for s in PIPELINE_ORDER] == [
        "user_input",
        "claim_extraction",
        "user_review_confirmation",
        "claim_classification",
        "source_routing",
        "hybrid_retrieval",
        "evidence_verification",
        "evidence_analysis",
        "verification_status",
        "final_validation_gate",
        "final_user_result",
    ]


def test_trusted_sources_allowlist_exact():
    assert set(TRUSTED_SOURCES) == set(TrustedSourceId)
    assert {s.value for s in TrustedSourceId} == {
        "quran",
        "tafsir_al_muyassar",
        "tafsir_ibn_kathir",
        "asbab_al_nuzul_al_wahidi",
        "al_muharrar_fi_asbab_al_nuzul",
        "dorar_hadith",
    }
    assert values(Provider) == ["quranpedia", "dorar_al_sunniyah"]
    by_provider = {sid: s.provider for sid, s in TRUSTED_SOURCES.items()}
    assert by_provider[TrustedSourceId.DORAR_HADITH] == Provider.DORAR_AL_SUNNIYAH
    assert all(
        p == Provider.QURANPEDIA
        for sid, p in by_provider.items()
        if sid != TrustedSourceId.DORAR_HADITH
    )


def test_source_boundary_quran_does_not_establish_sabab():
    quran = TRUSTED_SOURCES[TrustedSourceId.QURAN]
    assert quran.qualified_for == frozenset({ClaimType.QURAN})
    assert ClaimType.ASBAB_NUZUL not in quran.qualified_for


def test_allowlist_is_read_only():
    import pytest

    with pytest.raises(TypeError):
        TRUSTED_SOURCES[TrustedSourceId.QURAN] = None  # type: ignore[index]


def test_shared_contract_snapshot_is_up_to_date():
    """contracts/domain-contracts.json (used by the frontend) matches the backend."""
    assert contracts_export.SNAPSHOT_PATH.exists(), "run: python -m app.domain.contracts_export"
    assert contracts_export.SNAPSHOT_PATH.read_text(encoding="utf-8") == contracts_export.render()
