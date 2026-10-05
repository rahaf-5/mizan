"""Result builder: validated per-claim outcome + deterministic presentation (Tasks 5b, 7).

Adds, without changing any relationship or status: Evidence Strength signals (pipeline facts),
the result group, a claim-specific `why` and the `what_to_do` action.
"""

from __future__ import annotations

from app.domain.claim import ClassifiedClaim
from app.domain.enums import ClaimType, RetrievalAttemptStatus, SourceType
from app.domain.evidence import Evidence
from app.domain.results import VerificationOutcome
from app.domain.retrieval import RetrievalResult
from app.domain.trusted_sources import TRUSTED_SOURCES
from app.domain.validation import FinalValidationResult
from app.domain.verification import AnalysisResult, ClaimComponent, StatusDetermination
from app.pipeline.explanation import GROUP, WHAT_TO_DO, build_why, strength

TYPE_LABEL = {
    ClaimType.QURAN: "نص القرآن وموضعه",
    ClaimType.TAFSIR: "التفسير",
    ClaimType.ASBAB_NUZUL: "أسباب النزول",
    ClaimType.HADITH: "الحديث",
}


_PASSAGE_TYPES = {ClaimType.TAFSIR, ClaimType.ASBAB_NUZUL}


def verified_reference(components: list[ClaimComponent], evidence: list[Evidence]) -> str | None:
    """The ayah location(s) the official Quran source established for the claim's Quran
    components — copied from the evidence record's own reference, never composed."""
    quran = {
        (e.metadata.surah_number, e.metadata.ayah_number): e.reference
        for e in evidence
        if e.source_type == SourceType.QURAN
    }
    refs: list[str] = []
    for c in components:
        if c.claim_type != ClaimType.QURAN:
            continue
        for loc in c.verified_location:
            ref = quran.get((loc.surah_number, loc.ayah_number))
            if ref and ref not in refs:
                refs.append(ref)
    return "، ".join(refs) if refs else None


def limitations(retrieval: RetrievalResult) -> list[str]:
    """Approved tafsir/asbab sources that were searched successfully but hold no text for
    the anchor ayah at the provider (e.g. coverage gaps). Facts about the search only."""
    out: list[str] = []
    for a in retrieval.attempts:
        source = TRUSTED_SOURCES.get(a.source)
        if (
            source is None
            or a.status != RetrievalAttemptStatus.COMPLETED
            or a.candidate_count
            or not (source.qualified_for & _PASSAGE_TYPES)
        ):
            continue
        note = (
            f"لا يتضمن «{source.name_ar}» لدى المزوّد نصًا للآية المعنية، فلم يُستخدم في هذا التحقق."
        )
        if note not in out:
            out.append(note)
    return out


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
            verified_reference=verified_reference(analysis.components, evidence),
            limitations=limitations(retrieval),
        )
