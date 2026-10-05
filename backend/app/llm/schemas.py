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

from app.domain.enums import ClaimType, ExtractionStatus, ProvidedEvidenceType


class LLMTask(str, Enum):
    CLAIM_EXTRACTION = "claim_extraction"
    CLASSIFICATION_ASSISTANCE = "classification_assistance"
    CONSTRAINED_EVIDENCE_ANALYSIS = "constrained_evidence_analysis"
    EXPLANATION_GENERATION = "explanation_generation"
    ALTERNATIVE_WORDING = "alternative_wording"


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


class AyahHintDraft(LLMOutput):
    """An ayah the claim quotes or names — a RETRIEVAL HINT only (validated, never evidence)."""

    surah_number: int = Field(description="Surah number (1-114).")
    ayah_start: int = Field(description="First ayah number.")
    ayah_end: int | None = Field(
        default=None, description="Last ayah number for a short range, else null."
    )


class ClassificationSuggestion(LLMOutput):
    suggested_claim_type: ClaimType | None = Field(
        default=None,
        description=(
            "Main claim type: quran | tafsir | asbab_nuzul | hadith, or null if the claim is "
            "none of these."
        ),
    )
    additional_claim_types: list[ClaimType] = Field(
        default_factory=list,
        description="Other claim types the SAME claim also asserts (composite claim), else [].",
    )
    ayah_hints: list[AyahHintDraft] = Field(
        default_factory=list,
        max_length=10,
        description="Ayahs the claim quotes or clearly refers to (lookup hints only), else [].",
    )
    rationale: str = Field(min_length=1, description="One short sentence.")


# --- Constrained evidence analysis -----------------------------------------


class AnalysisRelation(str, Enum):
    """LLM-side relation labels. `unrelated` items are dropped (never shown, never counted)."""

    SUPPORTS = "supports"
    PARTIALLY_SUPPORTS = "partially_supports"
    CONTRADICTS = "contradicts"
    INSUFFICIENT = "insufficient"
    UNRELATED = "unrelated"


class ClaimComponentDraft(LLMOutput):
    component_id: str = Field(description="Short id, e.g. c1.")
    text: str = Field(
        description="ONE assertion, copied VERBATIM as a contiguous span of the claim text."
    )
    claim_type: ClaimType = Field(description="tafsir or asbab_nuzul.")


class EvidenceJudgementDraft(LLMOutput):
    item: str = Field(description="Label of the source passage, e.g. E1.")
    component_id: str
    relation: AnalysisRelation
    segments: list[str] = Field(
        default_factory=list,
        max_length=3,
        description=(
            'Ids of 1-3 CONSECUTIVE numbered segments of THAT passage (e.g. ["E2.3", "E2.4"]) '
            "whose exact text the relation rests on. Required for supports, partially_supports "
            "and contradicts; [] otherwise."
        ),
    )
    supported_part: str | None = Field(default=None, description="For partially_supports.")
    unsupported_part: str | None = Field(default=None, description="For partially_supports.")
    rationale: str = Field(min_length=1, description="One short sentence, based only on the span.")


class EvidenceAnalysisDraft(LLMOutput):
    """Constrained analysis of GIVEN passages against GIVEN claim components. Not evidence."""

    components: list[ClaimComponentDraft] = Field(default_factory=list, max_length=5)
    judgements: list[EvidenceJudgementDraft] = Field(default_factory=list, max_length=40)


# --- Explanation generation -------------------------------------------------


class ExplanationDraft(LLMOutput):
    """User-facing wording; must be grounded in the given evidence ids only."""

    why: str = Field(min_length=1)
    what_to_do: str = Field(min_length=1)
    grounded_in_evidence_ids: list[str] = Field(default_factory=list)


# --- Alternative wording ------------------------------------------------------


class AlternativeWordingDraft(LLMOutput):
    """A PROPOSED rewording. Never trusted: it is re-verified through the full pipeline."""

    proposed_claim_text: str = Field(
        description=(
            "One Arabic claim that states ONLY what the given excerpts establish, close to the "
            "user's wording. Empty string if no reliable rewording is possible."
        )
    )
    rationale: str = Field(min_length=1, description="One short sentence.")


#: Output schema registered for each task.
TASK_OUTPUT_SCHEMAS: dict[LLMTask, type[LLMOutput]] = {
    LLMTask.CLAIM_EXTRACTION: ClaimExtractionDraft,
    LLMTask.CLASSIFICATION_ASSISTANCE: ClassificationSuggestion,
    LLMTask.CONSTRAINED_EVIDENCE_ANALYSIS: EvidenceAnalysisDraft,
    LLMTask.EXPLANATION_GENERATION: ExplanationDraft,
    LLMTask.ALTERNATIVE_WORDING: AlternativeWordingDraft,
}
