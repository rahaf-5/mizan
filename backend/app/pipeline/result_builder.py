"""Result builder (Task 5b): validated per-claim outcome; presentation fields stay empty."""

from __future__ import annotations

from app.domain.claim import ClassifiedClaim
from app.domain.results import VerificationOutcome
from app.domain.retrieval import RetrievalResult
from app.domain.validation import FinalValidationResult
from app.domain.verification import AnalysisResult, StatusDetermination


class VerificationResultBuilder:
    async def build(
        self,
        claim: ClassifiedClaim,
        retrieval: RetrievalResult,
        analysis: AnalysisResult,
        determination: StatusDetermination,
        validation: FinalValidationResult,
    ) -> VerificationOutcome:
        by_id = {c.evidence.evidence_id: c.evidence for c in retrieval.candidates}
        used = sorted(
            analysis.referenced_evidence_ids() | {a.evidence_id for a in analysis.assessments}
        )
        return VerificationOutcome(
            claim_id=claim.claim_id,
            confirmed_claim_text=claim.confirmed_claim_text,
            status=determination.status,
            analysis=analysis,
            validation=validation,
            evidence=[by_id[e] for e in used if e in by_id],
        )
