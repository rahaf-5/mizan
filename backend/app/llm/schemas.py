"""Structured outputs an LLM is allowed to produce.

Every LLM output type subclasses `LLMOutput`. By design (and enforced by
tests/test_llm_contracts.py) none of them can carry `Evidence`,
`CandidateEvidence`, references, URLs, citations or hadith gradings:
citations/references come only from verified source metadata.
Outputs are SUGGESTIONS that the owning pipeline stage validates.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ClaimType, EvidenceRelationship, ExtractionStatus, ProvidedEvidenceType


class LLMTask(str, Enum):
    CLAIM_EXTRACTION = "claim_extraction"
    CLASSIFICATION_ASSISTANCE = "classification_assistance"
    CONSTRAINED_EVIDENCE_ANALYSIS = "constrained_evidence_analysis"
    EXPLANATION_GENERATION = "explanation_generation"


class LLMOutput(BaseModel):
    """Base class for all structured LLM outputs."""

    model_config = ConfigDict(frozen=True, extra="forbid")


# --- Claim extraction -------------------------------------------------------


class ExtractedClaimDraft(LLMOutput):
    """One verifiable religious claim found in the user's content.

    Extraction is NOT verification: no verdicts, gradings, citations or
    evidence. `source_excerpt` must be copied verbatim from the content so the
    claim can be checked as grounded (no invented claims).
    """

    extracted_claim_text: str = Field(
        min_length=1,
        max_length=1000,
        description=(
            "One atomic, self-contained religious claim in Arabic, preserving the user's meaning "
            "and wording; no corrections, no judgement, no added information."
        ),
    )
    source_excerpt: str = Field(
        min_length=1,
        max_length=2000,
        description="The exact span copied verbatim from the content that states this claim.",
    )
    extraction_status: ExtractionStatus = Field(
        description="clear | ambiguous (meaning unclear) | incomplete (cut off / missing parts).",
    )
    #: An ayah/hadith quoted IN THE USER'S CONTENT as support (user-provided, not evidence).
    provided_evidence_type: ProvidedEvidenceType | None = Field(
        default=None, description="quran | hadith if the content quotes one as support, else null."
    )
    provided_evidence_text: str | None = Field(
        default=None, max_length=2000, description="The quoted ayah/hadith text exactly as written."
    )
    #: Reference text exactly as written by the user, if any.
    user_written_reference: str | None = Field(
        default=None, max_length=500, description="A reference written in the content, verbatim."
    )


class ClaimExtractionDraft(LLMOutput):
    claims: list[ExtractedClaimDraft] = Field(default_factory=list, max_length=50)


# --- Classification assistance ---------------------------------------------


class ClassificationSuggestion(LLMOutput):
    suggested_claim_type: ClaimType | None = None
    rationale: str = Field(min_length=1)


# --- Constrained evidence analysis -----------------------------------------


class RelationshipSuggestion(LLMOutput):
    """Suggestion about ONE evidence item that was given to the model (by id)."""

    evidence_id: str
    relationship: EvidenceRelationship
    supported_part: str | None = None
    unsupported_part: str | None = None
    rationale: str = Field(min_length=1)


class ConstrainedAnalysisDraft(LLMOutput):
    suggestions: list[RelationshipSuggestion] = Field(default_factory=list)


# --- Explanation generation -------------------------------------------------


class ExplanationDraft(LLMOutput):
    """User-facing wording; must be grounded in the given evidence ids only."""

    why: str = Field(min_length=1)
    what_to_do: str = Field(min_length=1)
    grounded_in_evidence_ids: list[str] = Field(default_factory=list)


#: Output schema registered for each task.
TASK_OUTPUT_SCHEMAS: dict[LLMTask, type[LLMOutput]] = {
    LLMTask.CLAIM_EXTRACTION: ClaimExtractionDraft,
    LLMTask.CLASSIFICATION_ASSISTANCE: ClassificationSuggestion,
    LLMTask.CONSTRAINED_EVIDENCE_ANALYSIS: ConstrainedAnalysisDraft,
    LLMTask.EXPLANATION_GENERATION: ExplanationDraft,
}
