"""Evidence Verification, Evidence Analysis and Verification Status models (spec §7–§9, §14).

- Each candidate is assessed independently against the confirmed claim.
- Evidence Analysis compares assessments and creates NO new evidence: every
  evidence id it references must come from the assessments.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import EvidenceRelationship, EvidenceStrengthSignal, VerificationStatus


class StrengthSignalObservation(BaseModel):
    """One observed Evidence Strength signal and the pipeline fact behind it.

    Deliberately has no score/level: thresholds are not yet defined (spec §14).
    """

    model_config = ConfigDict(frozen=True)

    signal: EvidenceStrengthSignal
    basis: str = Field(min_length=1, description="Pipeline fact this observation is based on")


class EvidenceStrengthAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    observations: list[StrengthSignalObservation] = Field(default_factory=list)


class EvidenceAssessment(BaseModel):
    """Evidence Verification output for ONE candidate evidence item."""

    model_config = ConfigDict(frozen=True)

    evidence_id: str
    relationship: EvidenceRelationship
    #: Claim component this assessment concerns (None = whole claim).
    claim_component: str | None = None
    #: For partially_supports: the supported part and the unsupported/unproven part.
    supported_part: str | None = None
    unsupported_part: str | None = None
    #: Explanation grounded in the evidence (no invented assumptions).
    rationale: str = Field(min_length=1)
    strength: EvidenceStrengthAssessment = Field(default_factory=EvidenceStrengthAssessment)

    @model_validator(mode="after")
    def _partial_requires_parts(self) -> EvidenceAssessment:
        if self.relationship == EvidenceRelationship.PARTIALLY_SUPPORTS and not (
            self.supported_part and self.unsupported_part
        ):
            raise ValueError("partially_supports requires supported_part and unsupported_part")
        return self


class ComponentFinding(BaseModel):
    """A claim component and the evidence associated with it."""

    model_config = ConfigDict(frozen=True)

    component_text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)


class EvidenceConflict(BaseModel):
    """Genuine conflict between trusted evidence items (Evidence <-> Evidence)."""

    model_config = ConfigDict(frozen=True)

    evidence_ids: list[str] = Field(min_length=2)
    description: str = Field(min_length=1)


class AttributedRuling(BaseModel):
    """A scholarly ruling (e.g. hadith grading) preserved with its attribution.

    Copied from evidence metadata; never generated or chosen by the model.
    """

    model_config = ConfigDict(frozen=True)

    evidence_id: str
    scholar: str = Field(min_length=1)
    ruling: str = Field(min_length=1)


class AnalysisResult(BaseModel):
    """Structured `analysis_result` (spec §9)."""

    model_config = ConfigDict(frozen=True)

    claim_id: str
    assessments: list[EvidenceAssessment] = Field(default_factory=list)
    supported_components: list[ComponentFinding] = Field(default_factory=list)
    unsupported_components: list[ComponentFinding] = Field(default_factory=list)
    contradicted_components: list[ComponentFinding] = Field(default_factory=list)
    evidence_conflicts: list[EvidenceConflict] = Field(default_factory=list)
    attributed_rulings: list[AttributedRuling] = Field(default_factory=list)

    def referenced_evidence_ids(self) -> set[str]:
        ids: set[str] = set()
        for group in (
            self.supported_components,
            self.unsupported_components,
            self.contradicted_components,
        ):
            for f in group:
                ids.update(f.evidence_ids)
        for c in self.evidence_conflicts:
            ids.update(c.evidence_ids)
        ids.update(r.evidence_id for r in self.attributed_rulings)
        return ids

    @model_validator(mode="after")
    def _no_new_evidence(self) -> AnalysisResult:
        assessed = {a.evidence_id for a in self.assessments}
        unknown = self.referenced_evidence_ids() - assessed
        if unknown:
            raise ValueError(
                f"analysis references evidence that was not assessed: {sorted(unknown)} "
                "(Evidence Analysis never creates new evidence)"
            )
        return self


class StatusDetermination(BaseModel):
    """Output of the Verification Status stage — one of the six approved statuses."""

    model_config = ConfigDict(frozen=True)

    claim_id: str
    status: VerificationStatus
    #: Evidence the status is based on (empty for no_evidence_found).
    basis_evidence_ids: list[str] = Field(default_factory=list)
