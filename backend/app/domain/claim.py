"""Claim models (spec §3).

Gate: verification accepts only `ConfirmedClaim`, which cannot be built from a
pending / empty / deselected claim. Verification relies only on
`confirmed_claim_text`.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import (
    CONFIRMED_STATUSES,
    ClaimType,
    ExtractionStatus,
    ProvidedEvidenceType,
    UserConfirmationStatus,
)
from app.domain.errors import ClaimNotConfirmedError


def new_claim_id() -> str:
    return str(uuid.uuid4())


class ProvidedEvidence(BaseModel):
    """An ayah/hadith that the user's content cites as evidence, separated from the claim.

    It must later be checked for authenticity AND for its relationship to the
    claim. Verified Evidence != Automatically Supporting Evidence.
    """

    model_config = ConfigDict(frozen=True)

    provided_evidence_type: ProvidedEvidenceType
    provided_evidence_text: str = Field(min_length=1)


class Claim(BaseModel):
    """A claim as it moves through extraction and user review."""

    claim_id: str = Field(default_factory=new_claim_id)
    original_text: str
    #: Null for claims manually added by the user during Claim Review.
    extracted_claim_text: str | None = None
    #: The only text verification may use. Set when the user confirms/edits.
    confirmed_claim_text: str | None = None
    #: Null until the Claim Classification stage (approved).
    claim_type: ClaimType | None = None
    provided_evidence: ProvidedEvidence | None = None
    #: User-entered reference, kept exactly as entered. Never silently corrected.
    provided_reference: str | None = None
    #: Reference established from trusted-source metadata (set by later stages only).
    verified_reference: str | None = None
    #: Null for manually added claims (not produced by extraction).
    extraction_status: ExtractionStatus | None = None
    user_confirmation_status: UserConfirmationStatus = UserConfirmationStatus.PENDING
    #: Claim Review "deselect from verification" (approved addition).
    selected_for_verification: bool = True


class ConfirmedClaim(BaseModel):
    """A user-confirmed claim — the only claim shape later stages accept."""

    model_config = ConfigDict(frozen=True)

    claim_id: str
    confirmed_claim_text: str
    user_confirmation_status: UserConfirmationStatus
    claim_type: ClaimType | None = None
    provided_evidence: ProvidedEvidence | None = None
    provided_reference: str | None = None

    @field_validator("confirmed_claim_text")
    @classmethod
    def _text_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("confirmed_claim_text must not be empty")
        return v

    @field_validator("user_confirmation_status")
    @classmethod
    def _must_be_confirmed(cls, v: UserConfirmationStatus) -> UserConfirmationStatus:
        if v not in CONFIRMED_STATUSES:
            raise ValueError("claim must be confirmed or edited by the user before verification")
        return v


class ClassifiedClaim(ConfirmedClaim):
    """A confirmed claim after Claim Classification: `claim_type` is required."""

    claim_type: ClaimType  # type: ignore[assignment]

    @model_validator(mode="after")
    def _type_required(self) -> ClassifiedClaim:
        if self.claim_type is None:  # pragma: no cover - enforced by type
            raise ValueError("claim_type is required after classification")
        return self


def confirm_for_verification(claim: Claim) -> ConfirmedClaim:
    """User Review & Confirmation gate (spec §2: No Verification Before Claim Confirmation).

    Raises ClaimNotConfirmedError if the claim is pending, has no confirmed
    text, or was deselected from verification.
    """
    if not claim.selected_for_verification:
        raise ClaimNotConfirmedError(f"claim {claim.claim_id} is not selected for verification")
    if claim.user_confirmation_status not in CONFIRMED_STATUSES:
        raise ClaimNotConfirmedError(f"claim {claim.claim_id} has not been confirmed by the user")
    if not claim.confirmed_claim_text or not claim.confirmed_claim_text.strip():
        raise ClaimNotConfirmedError(f"claim {claim.claim_id} has no confirmed_claim_text")
    return ConfirmedClaim(
        claim_id=claim.claim_id,
        confirmed_claim_text=claim.confirmed_claim_text,
        user_confirmation_status=claim.user_confirmation_status,
        claim_type=claim.claim_type,
        provided_evidence=claim.provided_evidence,
        provided_reference=claim.provided_reference,
    )


def select_confirmed_claims(claims: list[Claim]) -> list[ConfirmedClaim]:
    """Return the selected claims as ConfirmedClaims.

    Deselected claims are skipped. A selected claim that is not confirmed is
    an error — it is never verified silently or in the background.
    """
    return [confirm_for_verification(c) for c in claims if c.selected_for_verification]
