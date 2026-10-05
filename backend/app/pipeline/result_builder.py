"""Result builder: validated per-claim outcome + deterministic presentation (Tasks 5b, 7).

Adds, without changing any relationship or status: Evidence Strength signals (pipeline facts),
the result group, a claim-specific `why` and the `what_to_do` action.
"""

from __future__ import annotations

from app.domain.claim import ClassifiedClaim
from app.domain.enums import ClaimType
from app.domain.results import VerificationOutcome
from app.domain.retrieval import RetrievalResult
from app.domain.validation import FinalValidationResult
from app.domain.verification import AnalysisResult, StatusDetermination
from app.pipeline.explanation import GROUP, WHAT_TO_DO, build_why, strength

TYPE_LABEL = {
    ClaimType.QURAN: "نص القرآن وموضعه",
    ClaimType.TAFSIR: "التفسير",
    ClaimType.ASBAB_NUZUL: "أسباب النزول",
    ClaimType.HADITH: "الحديث",
}


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
        evidence = [by_id[e] for e in used if e in by_id]
        comps = {c.component_id: c for c in analysis.components}
        assessments = [
            a.model_copy(
                update={
                    "strength": strength(
                        a,
                        by_id[a.evidence_id],
                        TYPE_LABEL[comps[a.component_id].claim_type]
                        if a.component_id in comps
                        else "",
                    )
                }
            )
            if a.evidence_id in by_id
            else a
            for a in analysis.assessments
        ]
        analysis = analysis.model_copy(update={"assessments": assessments})
        status = determination.status
        return VerificationOutcome(
            claim_id=claim.claim_id,
            confirmed_claim_text=claim.confirmed_claim_text,
            status=status,
            analysis=analysis,
            validation=validation,
            evidence=evidence,
            result_group=GROUP[status],
            why=build_why(status, analysis, evidence),
            what_to_do=WHAT_TO_DO[status],
        )
