"""Approved Mizan enumerations.

Values are taken verbatim from MIZAN_PRODUCT_SPEC.md. They are guarded by
tests/test_contracts.py and by the shared snapshot contracts/domain-contracts.json.
Do NOT add, remove, rename or merge values without explicit product approval.
"""

from __future__ import annotations

from enum import Enum


class _StrEnum(str, Enum):
    """str-valued Enum (Python 3.10 compatible stand-in for enum.StrEnum)."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


# --- Claims (spec §3) -------------------------------------------------------


class ClaimType(_StrEnum):
    QURAN = "quran"
    TAFSIR = "tafsir"
    ASBAB_NUZUL = "asbab_nuzul"
    HADITH = "hadith"


class ExtractionStatus(_StrEnum):
    CLEAR = "clear"
    AMBIGUOUS = "ambiguous"
    INCOMPLETE = "incomplete"


class UserConfirmationStatus(_StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EDITED = "edited"


#: Confirmation statuses that permit verification (approved: `edited` counts as confirmed).
CONFIRMED_STATUSES: frozenset[UserConfirmationStatus] = frozenset(
    {UserConfirmationStatus.CONFIRMED, UserConfirmationStatus.EDITED}
)


class ProvidedEvidenceType(_StrEnum):
    """Type of an ayah/hadith that the user's content itself cites as evidence (spec §3)."""

    QURAN = "quran"
    HADITH = "hadith"


# --- Evidence (spec §4) -----------------------------------------------------


class SourceType(_StrEnum):
    """`source_type` of a unified Evidence record."""

    QURAN = "quran"
    TAFSIR = "tafsir"
    ASBAB_NUZUL = "asbab_nuzul"
    HADITH = "hadith"


class AsbabRelationType(_StrEnum):
    """Distinguishes a direct sabab al-nuzul from contextual material (spec §4).

    Initial MVP representation. Extensible; no religious inference rules are
    built on top of this enum.
    """

    DIRECT_SABAB = "direct_sabab"
    CONTEXTUAL = "contextual"


# --- Retrieval (spec §6) ----------------------------------------------------


class RetrievalMethod(_StrEnum):
    EXACT = "exact"
    KEYWORD = "keyword"
    SEMANTIC = "semantic"


class RetrievalAttemptStatus(_StrEnum):
    """Technical status of one retrieval attempt (NOT an evidence judgement)."""

    COMPLETED = "completed"
    FAILED = "failed"


# --- Verification (spec §7, §8) ---------------------------------------------


class EvidenceRelationship(_StrEnum):
    """Relationship of ONE candidate evidence item to the confirmed claim (spec §7).

    `no_evidence_found` is deliberately NOT here: it is a retrieval outcome,
    not an evidence relationship.
    """

    SUPPORTS = "supports"
    PARTIALLY_SUPPORTS = "partially_supports"
    CONTRADICTS = "contradicts"
    INSUFFICIENT = "insufficient"


class VerificationStatus(_StrEnum):
    """The six approved internal verification statuses (spec §8).

    `contradicted`         = Claim <-> Evidence conflict.
    `conflicting_evidence` = Evidence <-> Evidence conflict.
    There is no "true/false", no "out_of_scope" and no "system_error" here:
    those are represented separately (see domain.results / domain.errors).
    """

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_EVIDENCE_FOUND = "no_evidence_found"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


class EvidenceStrengthSignal(_StrEnum):
    """Pipeline signals Evidence Strength must be based on (spec §14).

    Only the signals are modelled. No High/Medium/Low thresholds and no
    numeric confidence score are defined (pending product decision).
    """

    SOURCE_SUITABILITY = "source_suitability"
    DIRECTNESS = "directness"
    COMPLETENESS = "completeness"
    TRACEABILITY = "traceability"
    MATCH_QUALITY = "match_quality"
    AGREEMENT_OR_CONFLICT = "agreement_or_conflict"


# --- Final Validation Gate (spec §10) ---------------------------------------


class ValidationOutcome(_StrEnum):
    """Internal gate outcome. `abstain` is NOT a user-visible seventh status."""

    PASS = "pass"
    RETRY = "retry"
    ABSTAIN = "abstain"


class ValidationCheck(_StrEnum):
    """The seven checks required before any final result (spec §10)."""

    USES_CONFIRMED_CLAIM_TEXT = "uses_confirmed_claim_text"
    EVIDENCE_RELATES_TO_CLAIM = "evidence_relates_to_claim"
    SOURCE_APPROVED_AND_QUALIFIED = "source_approved_and_qualified"
    EVIDENCE_TRACEABLE = "evidence_traceable"
    REFERENCES_FROM_VERIFIED_METADATA = "references_from_verified_metadata"
    STATUS_MATCHES_EVIDENCE = "status_matches_evidence"
    WORDING_NOT_STRONGER_THAN_EVIDENCE = "wording_not_stronger_than_evidence"


class RetryReason(_StrEnum):
    """Fixable verification problems that justify a bounded retry (spec §10, examples)."""

    WEAK_RETRIEVAL = "weak_retrieval"
    MISSING_RETRIEVABLE_METADATA = "missing_retrievable_metadata"
    RETRIEVAL_STRATEGY_NOT_ATTEMPTED = "retrieval_strategy_not_attempted"


# --- Processing outcomes that are NOT verification statuses ------------------


class OutOfScopeReason(_StrEnum):
    """Why a claim is outside the current MVP's capabilities or source coverage.

    Out of Scope is a processing/routing outcome, NOT a verification status,
    and never means False. Initial representation; the rules that decide it
    are defined in later tasks.
    """

    UNSUPPORTED_CLAIM_CATEGORY = "unsupported_claim_category"
    OUTSIDE_SOURCE_COVERAGE = "outside_source_coverage"


class SystemErrorCode(_StrEnum):
    """Technical failures. Never converted into an evidence verdict (spec §17)."""

    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_NOT_CONNECTED = "source_not_connected"
    LLM_PROVIDER_ERROR = "llm_provider_error"
    OCR_ERROR = "ocr_error"
    DATABASE_ERROR = "database_error"
    STAGE_NOT_IMPLEMENTED = "stage_not_implemented"
    VERIFICATION_INCOMPLETE = "verification_incomplete"
    INTERNAL_ERROR = "internal_error"


# --- Presentation (spec §12) — mapping rules are Task 7 ----------------------


class ResultGroup(_StrEnum):
    """User-facing report groups. Kept separate from internal statuses.

    The status -> group mapping is NOT encoded here (spec §12 is not a pure
    function of status; e.g. "materially unsupported" wording). Task 7.
    """

    VERIFIED = "verified"  # 🟢 محتوى تم التحقق منه
    DO_NOT_USE_AS_WRITTEN = "do_not_use_as_written"  # 🔴 لا تستخدم هذه الادعاءات بصيغتها الحالية
    NEEDS_REVISION = "needs_revision"  # 🟡 تحتاج مراجعة قبل النشر
    NEEDS_EVIDENCE_REVIEW = "needs_evidence_review"  # ⚠️ تحتاج مراجعة الأدلة


# --- Input & pipeline -------------------------------------------------------


class CheckMode(_StrEnum):
    QUICK_CHECK = "quick_check"
    FULL_CONTENT = "full_content"


class InputType(_StrEnum):
    TEXT = "text"
    IMAGE = "image"


class PipelineStage(_StrEnum):
    """Approved core pipeline order (spec §11)."""

    USER_INPUT = "user_input"
    CLAIM_EXTRACTION = "claim_extraction"
    USER_REVIEW_CONFIRMATION = "user_review_confirmation"
    CLAIM_CLASSIFICATION = "claim_classification"
    SOURCE_ROUTING = "source_routing"
    HYBRID_RETRIEVAL = "hybrid_retrieval"
    EVIDENCE_VERIFICATION = "evidence_verification"
    EVIDENCE_ANALYSIS = "evidence_analysis"
    VERIFICATION_STATUS = "verification_status"
    FINAL_VALIDATION_GATE = "final_validation_gate"
    FINAL_USER_RESULT = "final_user_result"


#: Spec §11 order, used by tests and the orchestrator.
PIPELINE_ORDER: tuple[PipelineStage, ...] = tuple(PipelineStage)
