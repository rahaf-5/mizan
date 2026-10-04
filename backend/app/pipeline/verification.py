"""Evidence Verification (Task 5b).

Each qualified candidate is judged independently against verbatim components of the confirmed
claim:
  * Quran components — deterministic (`quran_checks.QuranVerifier`), no LLM;
  * tafsir / asbab components — Gemini constrained analysis of the top passages
    (max 3 per source, one analysis call per claim), validated by `PassageAnalyzer`.
Keyword-only candidates are NEVER judged: they are kept only as related/unverified addresses.
"""

from __future__ import annotations

from app.domain.claim import ClassifiedClaim
from app.domain.enums import ClaimType, ComponentKind, ComponentRole, RetrievalMatchBasis
from app.domain.retrieval import CandidateEvidence
from app.domain.trusted_sources import TrustedSourceId, get_trusted_source
from app.domain.verification import ClaimComponent, EvidenceAssessment, VerificationFindings
from app.llm.base import LLMProvider
from app.pipeline.passage_analysis import PassageAnalyzer
from app.pipeline.quran_checks import QuranVerifier
from app.sources.registry import AdapterRegistry

PASSAGE_TYPES = (ClaimType.TAFSIR, ClaimType.ASBAB_NUZUL)


class TrustedEvidenceVerifier:
    def __init__(
        self, registry: AdapterRegistry, provider: LLMProvider, *, max_per_source: int = 3
    ) -> None:
        self._registry = registry
        self._passages = PassageAnalyzer(provider)
        self._max_per_source = max_per_source

    async def verify(
        self, claim: ClassifiedClaim, candidates: list[CandidateEvidence]
    ) -> VerificationFindings:
        strong = [
            c
            for c in candidates
            if c.retrieval.match_basis not in (None, RetrievalMatchBasis.KEYWORD)
        ]
        weak = [c for c in candidates if c not in strong]
        components: list[ClaimComponent] = []
        assessments: list[EvidenceAssessment] = []
        required = claim.required_claim_types

        if ClaimType.QURAN in required:
            index = self._registry.adapter_for(TrustedSourceId.QURAN).quran_index()  # type: ignore[attr-defined]
            quran = [c for c in strong if c.evidence.trusted_source_id == TrustedSourceId.QURAN]
            comps, assess = QuranVerifier(index).verify(claim, quran)
            if any(t in PASSAGE_TYPES for t in required):
                # The quoted ayah / its location identifies WHICH ayah the tafsir / asbab
                # assertion concerns: context (anchor), not an independent assertion.
                comps = [c.model_copy(update={"role": ComponentRole.ANCHOR}) for c in comps]
            components += comps
            assessments += assess

        types = [t for t in required if t in PASSAGE_TYPES]
        if types:
            passages: list[CandidateEvidence] = []
            per_source: dict[TrustedSourceId, int] = {}
            for c in sorted(strong, key=lambda c: c.retrieval.retrieval_rank):
                sid = c.evidence.trusted_source_id
                if not (get_trusted_source(sid).qualified_for & set(types)):
                    continue
                if per_source.get(sid, 0) >= self._max_per_source:
                    continue
                per_source[sid] = per_source.get(sid, 0) + 1
                passages.append(c)
            if passages:
                comps, assess = await self._passages.analyze(claim, passages, types)
                components += comps
                assessments += assess
            else:
                for i, t in enumerate(types, start=1):
                    components.append(
                        ClaimComponent(
                            component_id=f"s{i}",
                            text=claim.confirmed_claim_text.strip(),
                            kind=ComponentKind.STATEMENT,
                            claim_type=t,
                            detail="لم يُعثر على مقاطع مؤهلة مرتبطة بآية محددة في المصادر المعتمدة.",
                        )
                    )
        return VerificationFindings(
            claim_id=claim.claim_id,
            components=components,
            assessments=assessments,
            related_unverified_addresses=sorted({c.evidence.source_address for c in weak}),
        )
