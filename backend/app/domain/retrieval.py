"""Hybrid Retrieval models (spec §6).

Retrieval produces Candidate Evidence, never a verdict.
Semantic Similarity != Verified Evidence. Weak Retrieval != False Claim.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import RetrievalAttemptStatus, RetrievalMatchBasis, RetrievalMethod
from app.domain.errors import SystemErrorInfo
from app.domain.evidence import AyahRef, Evidence
from app.domain.trusted_sources import TrustedSourceId


class RetrievalMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    retrieval_method: RetrievalMethod
    #: Raw similarity/match score from the retrieval method, if any. Scale is
    #: method-specific and it is NOT a truth score.
    similarity_score: float | None = None
    #: Rank after merge/dedup. Ranking prioritises verification; not a truth score.
    retrieval_rank: Annotated[int, Field(ge=1)]
    searched_source: TrustedSourceId
    #: Why this record was looked at (audit trail; not a relevance verdict).
    match_basis: RetrievalMatchBasis | None = None
    #: For tafsir/asbab passages: the validated ayah the passage was fetched for.
    anchor_ayah: AyahRef | None = None


class CandidateEvidence(BaseModel):
    """Evidence found by retrieval, not yet verified against the claim."""

    model_config = ConfigDict(frozen=True)

    evidence: Evidence
    retrieval: RetrievalMetadata

    @model_validator(mode="after")
    def _searched_source_matches(self) -> CandidateEvidence:
        if self.retrieval.searched_source != self.evidence.trusted_source_id:
            raise ValueError("searched_source must match the evidence's trusted source")
        return self


class RetrievalAttempt(BaseModel):
    """One search attempt against one approved source."""

    model_config = ConfigDict(frozen=True)

    source: TrustedSourceId
    method: RetrievalMethod
    #: Query actually sent. May be a reformulation; confirmed_claim_text is never changed.
    query_text: str
    is_reformulation: bool = False
    status: RetrievalAttemptStatus
    candidate_count: Annotated[int, Field(ge=0)] = 0
    #: Present only for technical failures (status=failed).
    error: SystemErrorInfo | None = None

    @model_validator(mode="after")
    def _error_iff_failed(self) -> RetrievalAttempt:
        failed = self.status == RetrievalAttemptStatus.FAILED
        if failed and self.error is None:
            raise ValueError("a failed attempt must carry a SystemErrorInfo")
        if not failed and self.error is not None:
            raise ValueError("only failed attempts may carry an error")
        return self


class RetrievalResult(BaseModel):
    """Output of Hybrid Retrieval for one claim."""

    model_config = ConfigDict(frozen=True)

    claim_id: str
    candidates: list[CandidateEvidence] = Field(default_factory=list)
    attempts: list[RetrievalAttempt] = Field(default_factory=list)
    #: Recorded when retrieval stayed weak after the allowed strategies (spec §6).
    insufficient_retrieval: bool = False
    #: Ayahs (validated against the official Quran source) used to anchor retrieval.
    anchor_ayahs: list[AyahRef] = Field(default_factory=list)
    #: LLM retrieval hints rejected because they do not exist in the official Quran source.
    discarded_hint_count: int = Field(default=0, ge=0)
    #: Semantic search is not available in the MVP; recorded so that its absence is explicit.
    semantic_search_attempted: bool = False

    @property
    def all_attempts_failed(self) -> bool:
        """True if no attempt completed — a technical failure, NOT no_evidence_found."""
        return bool(self.attempts) and all(
            a.status == RetrievalAttemptStatus.FAILED for a in self.attempts
        )

    @property
    def has_failed_attempts(self) -> bool:
        return any(a.status == RetrievalAttemptStatus.FAILED for a in self.attempts)

    @property
    def no_candidates_after_completed_search(self) -> bool:
        """Retrieval outcome: completed search(es) in approved sources returned nothing.

        This is the retrieval-level signal behind `no_evidence_found`; it is
        not an evidence relationship and never means False.
        """
        completed = any(a.status == RetrievalAttemptStatus.COMPLETED for a in self.attempts)
        return completed and not self.candidates
