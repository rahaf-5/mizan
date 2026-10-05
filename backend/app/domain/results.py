"""Per-claim outcomes and the Final User Result (spec §8, §10, §12, §17).

A claim ends in exactly one of three structurally separate outcomes:
  - VerificationOutcome : one of the six evidence-based statuses (validated)
  - OutOfScopeOutcome   : outside MVP capabilities/source coverage (NOT a status, NOT False)
  - SystemErrorOutcome  : technical failure (NOT insufficient_evidence)
  - RequiredSourceUnavailableOutcome : the claim is within scope, but a trusted source it
    REQUIRES is currently unavailable (e.g. Hadith/Dorar). Mizan abstains explicitly.
    NOT a status, NOT out of scope, NOT a system error, NOT contradiction/falsehood.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import (
    ClaimType,
    OutOfScopeReason,
    ResultGroup,
    ValidationOutcome,
    VerificationStatus,
)
from app.domain.errors import SystemErrorInfo
from app.domain.evidence import Evidence
from app.domain.trusted_sources import TrustedSourceId, get_trusted_source
from app.domain.validation import FinalValidationResult
from app.domain.verification import AnalysisResult


class VerificationOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["verification"] = "verification"
    claim_id: str
    confirmed_claim_text: str = Field(min_length=1)
    status: VerificationStatus
    analysis: AnalysisResult
    validation: FinalValidationResult
    #: Every evidence item shown for this claim (full traceable records).
    evidence: list[Evidence] = Field(default_factory=list)
    # --- Presentation fields: filled in Task 7 (must be traceable to evidence) ---
    result_group: ResultGroup | None = None
    why: str | None = None
    what_to_do: str | None = None
    #: Location established by the trusted Quran source (spec §3 `verified_reference`). Shown
    #: next to the user's own wording/reference; the user's reference is never rewritten.
    verified_reference: str | None = None
    #: Relevant limitations of this result (spec §17), e.g. an approved source that has no
    #: text for the anchor ayah at the provider. Facts only; never a verdict.
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validated_and_traceable(self) -> VerificationOutcome:
        if self.validation.claim_id != self.claim_id or self.analysis.claim_id != self.claim_id:
            raise ValueError("analysis/validation belong to a different claim")
        if self.validation.outcome == ValidationOutcome.RETRY:
            raise ValueError(
                "a retry outcome is not final; No Final Result Without Final Validation"
            )
        if (
            self.validation.outcome == ValidationOutcome.ABSTAIN
            and self.validation.abstained_to != self.status
        ):
            raise ValueError("abstained result must use the status it was mapped to")
        evidence_ids = {e.evidence_id for e in self.evidence}
        assessed = {a.evidence_id for a in self.analysis.assessments}
        if not assessed <= evidence_ids:
            raise ValueError("every assessed evidence item must be included as a traceable record")
        return self


class OutOfScopeOutcome(BaseModel):
    """The current MVP cannot verify this claim. Out of Scope != False."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["out_of_scope"] = "out_of_scope"
    claim_id: str
    reason: OutOfScopeReason
    detail: str | None = None


class SystemErrorOutcome(BaseModel):
    """Verification could not be completed for technical reasons. Allows retry."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["system_error"] = "system_error"
    claim_id: str
    error: SystemErrorInfo


class RequiredSourceUnavailableOutcome(BaseModel):
    """Explicit abstention: a REQUIRED trusted source is currently unavailable.

    The claim may be fully within Mizan's scope. Absence of evidence from an
    unavailable source is never contradiction, falsehood or ordinary
    insufficient/no evidence. No verdict is produced for the claim.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["required_source_unavailable"] = "required_source_unavailable"
    claim_id: str
    confirmed_claim_text: str = Field(min_length=1)
    #: Every claim type the claim requires (e.g. quran + hadith for a composite claim).
    required_claim_types: list[ClaimType] = Field(min_length=1)
    #: The required approved sources that are unavailable.
    unavailable_sources: list[TrustedSourceId] = Field(min_length=1)
    detail: str | None = None

    @model_validator(mode="after")
    def _really_required_and_unavailable(self) -> RequiredSourceUnavailableOutcome:
        for sid in self.unavailable_sources:
            src = get_trusted_source(sid)
            if not (src.qualified_for & set(self.required_claim_types)):
                raise ValueError(f"{sid.value} is not required by this claim's types")
        return self


ClaimOutcome = Annotated[
    VerificationOutcome | OutOfScopeOutcome | SystemErrorOutcome | RequiredSourceUnavailableOutcome,
    Field(discriminator="kind"),
]


class FinalUserResult(BaseModel):
    """Result of one verification run over the user's confirmed claims."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    outcomes: list[ClaimOutcome] = Field(default_factory=list)
    #: Relevant limitations to surface, e.g. a partially failed source (spec §17).
    limitations: list[str] = Field(default_factory=list)
