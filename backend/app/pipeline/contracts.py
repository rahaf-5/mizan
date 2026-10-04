"""Typed stage contracts for the approved core pipeline (spec §11).

User Input -> Claim Extraction -> User Review & Confirmation -> Claim Classification
-> Source Routing -> Hybrid Retrieval -> Evidence Verification -> Evidence Analysis
-> Verification Status -> Final Validation Gate -> Final User Result

Each stage has ONE responsibility and passes structured data to the next.
Stages after confirmation accept only ConfirmedClaim / ClassifiedClaim, so an
unconfirmed claim cannot reach verification.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.domain.claim import Claim, ClassifiedClaim, ConfirmedClaim
from app.domain.inputs import ExtractionInput
from app.domain.results import ClaimOutcome, OutOfScopeOutcome, RequiredSourceUnavailableOutcome
from app.domain.retrieval import CandidateEvidence, RetrievalResult
from app.domain.routing import SourceRoutingPlan
from app.domain.validation import FinalValidationResult
from app.domain.verification import AnalysisResult, StatusDetermination, VerificationFindings


class ClaimExtractionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    claims: list[Claim] = Field(default_factory=list)
    #: Quick Check received a paragraph / several claims -> suggest Full Content Check (spec §2A).
    suggest_full_content_check: bool = False
    #: Model-proposed claims dropped because they were not found in the submitted content.
    discarded_ungrounded_count: int = Field(default=0, ge=0)


@runtime_checkable
class ClaimExtractor(Protocol):
    """Extract verifiable claims; split multiple independent claims; separate provided evidence."""

    async def extract(self, data: ExtractionInput) -> ClaimExtractionResult: ...


@runtime_checkable
class ClaimClassifier(Protocol):
    """Assign claim_type, or decide the claim is out of the MVP's scope."""

    async def classify(self, claim: ConfirmedClaim) -> ClassifiedClaim | OutOfScopeOutcome: ...


@runtime_checkable
class SourceRouter(Protocol):
    """Route a classified claim only to qualified, AVAILABLE approved sources.

    If a source the claim requires is unavailable, return RequiredSourceUnavailableOutcome
    (explicit abstention; never a status, never Out of Scope).
    """

    async def route(
        self, claim: ClassifiedClaim
    ) -> SourceRoutingPlan | OutOfScopeOutcome | RequiredSourceUnavailableOutcome: ...


@runtime_checkable
class HybridRetriever(Protocol):
    """Exact -> Keyword -> Semantic (when appropriate) -> merge/dedup/rank. Never a verdict."""

    async def retrieve(
        self, claim: ClassifiedClaim, plan: SourceRoutingPlan, *, attempt: int = 0
    ) -> RetrievalResult: ...


@runtime_checkable
class EvidenceVerifier(Protocol):
    """Assess each qualified candidate independently against verbatim claim components."""

    async def verify(
        self, claim: ClassifiedClaim, candidates: list[CandidateEvidence]
    ) -> VerificationFindings: ...


@runtime_checkable
class EvidenceAnalyzer(Protocol):
    """Compare assessments into a structured analysis_result. Creates no evidence."""

    async def analyze(
        self, claim: ClassifiedClaim, findings: VerificationFindings
    ) -> AnalysisResult: ...


@runtime_checkable
class StatusDeterminer(Protocol):
    """Map analysis + retrieval facts to one of the six approved statuses."""

    async def determine(
        self, claim: ClassifiedClaim, analysis: AnalysisResult, retrieval: RetrievalResult
    ) -> StatusDetermination: ...


@runtime_checkable
class FinalValidationGate(Protocol):
    """Validate the result (pass / retry / abstain). Creates no evidence.

    Locked retry-exhaustion rule (technical failure != weak or missing evidence):
      * `retries_remaining` tells the gate how many bounded retries are left
        (from configuration, never hardcoded).
      * When the system operated correctly and the remaining limitation is
        evidentiary, the gate must ABSTAIN (internally) and map to the
        appropriate approved status, e.g. insufficient_evidence or
        no_evidence_found — it must not return `retry` with no budget left.
      * Returning `retry` with retries_remaining == 0 is reserved for a
        technical/system failure that prevents reliable verification; the
        orchestrator turns it into system_error(verification_incomplete).
    """

    async def validate(
        self,
        claim: ClassifiedClaim,
        retrieval: RetrievalResult,
        analysis: AnalysisResult,
        determination: StatusDetermination,
        *,
        retry_count: int,
        retries_remaining: int,
    ) -> FinalValidationResult: ...


@runtime_checkable
class ResultBuilder(Protocol):
    """Build the validated per-claim outcome for the Final User Result."""

    async def build(
        self,
        claim: ClassifiedClaim,
        retrieval: RetrievalResult,
        analysis: AnalysisResult,
        determination: StatusDetermination,
        validation: FinalValidationResult,
    ) -> ClaimOutcome: ...
