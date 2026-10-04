"""Hybrid Retrieval over the approved, AVAILABLE sources (Task 5a).

Produces Candidate Evidence only — never a verdict. Strategy (spec §6):
  1. Exact: quoted ayah text (normalised, >= 4 consecutive words), explicit surah/ayah
     references, and LLM retrieval hints validated against the official Quran (invalid hints
     are discarded and counted). These give the ayah ANCHORS.
  2. Keyword: idf-weighted keyword overlap — used only when exact strategies found nothing
     (or on a retry). Weak retrieval is flagged, never treated as "false".
  3. Semantic: not available in the MVP; recorded as not attempted.
Quran evidence comes from the official Mushaf 1 data; tafsir/asbab passages are fetched LIVE
for each anchor ayah from the bound Quranpedia book. Results are merged, deduplicated
(Quran by ayah id, passages by exact-text fingerprint) and ranked per source. Ranking
prioritises verification; it is not a truth score.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core_logging import get_logger
from app.domain.claim import ClassifiedClaim
from app.domain.enums import (
    ClaimType,
    PipelineStage,
    RetrievalAttemptStatus,
    RetrievalMatchBasis,
    RetrievalMethod,
)
from app.domain.errors import MizanError
from app.domain.evidence import AyahRef
from app.domain.retrieval import (
    CandidateEvidence,
    RetrievalAttempt,
    RetrievalMetadata,
    RetrievalResult,
)
from app.domain.routing import SourceRoutingPlan
from app.domain.trusted_sources import TrustedSourceId
from app.sources.base import SourceHit, SourceQuery
from app.sources.registry import AdapterRegistry

log = get_logger("pipeline.retrieval")

_BASIS_PRIORITY = {
    RetrievalMatchBasis.QUOTED_TEXT: 0,
    RetrievalMatchBasis.EXPLICIT_REFERENCE: 1,
    RetrievalMatchBasis.RETRIEVAL_HINT: 2,
    RetrievalMatchBasis.KEYWORD: 3,
}


@dataclass(frozen=True)
class _Anchor:
    ref: AyahRef
    basis: RetrievalMatchBasis


class TrustedSourceRetriever:
    def __init__(
        self,
        registry: AdapterRegistry,
        *,
        max_anchor_ayahs: int = 5,
        keyword_anchor_limit: int = 3,
        max_quran_candidates: int = 10,
        max_passages_per_source: int = 8,
    ) -> None:
        self._registry = registry
        self._max_anchors = max_anchor_ayahs
        self._kw_anchor_limit = keyword_anchor_limit
        self._max_quran = max_quran_candidates
        self._max_passages = max_passages_per_source

    async def retrieve(
        self, claim: ClassifiedClaim, plan: SourceRoutingPlan, *, attempt: int = 0
    ) -> RetrievalResult:
        attempts: list[RetrievalAttempt] = []
        hits: dict[TrustedSourceId, list[SourceHit]] = {}
        quran = self._registry.adapter_for(TrustedSourceId.QURAN)
        claim_text = claim.confirmed_claim_text
        quoted = claim.provided_evidence.provided_evidence_text if claim.provided_evidence else None

        try:
            index = quran.quran_index()  # type: ignore[attr-defined]
        except MizanError as exc:
            for route in plan.routes:
                for sid in route.sources:
                    attempts.append(_failed(sid, RetrievalMethod.EXACT, claim_text, exc))
            return RetrievalResult(claim_id=claim.claim_id, attempts=attempts)

        # ---- 1. exact anchors (quotes, explicit references, validated hints)
        anchors: list[_Anchor] = []

        def add_anchor(ref: AyahRef, basis: RetrievalMatchBasis) -> None:
            if all(a.ref.quranpedia_ayah_id != ref.quranpedia_ayah_id for a in anchors):
                anchors.append(_Anchor(ref, basis))

        quote_matches = []
        for text in filter(None, [quoted, claim_text]):
            quote_matches.extend(index.find_quotes(text, limit=10))
        quote_matches.sort(key=lambda m: -m.matched_words)
        for m in quote_matches:
            for ayah in m.ayahs:
                add_anchor(ayah.ref, RetrievalMatchBasis.QUOTED_TEXT)
        ref_text = " ".join(filter(None, [claim_text, claim.provided_reference]))
        for ayah in index.parse_references(ref_text):
            add_anchor(ayah.ref, RetrievalMatchBasis.EXPLICIT_REFERENCE)
        discarded_hints = 0
        for hint in claim.retrieval_hints:
            resolved = index.validate_hint(hint)
            if resolved is None:
                discarded_hints += 1
                continue
            for ayah in resolved:
                add_anchor(ayah.ref, RetrievalMatchBasis.RETRIEVAL_HINT)
        attempts.append(
            RetrievalAttempt(
                source=TrustedSourceId.QURAN,
                method=RetrievalMethod.EXACT,
                query_text=claim_text,
                status=RetrievalAttemptStatus.COMPLETED,
                candidate_count=len(anchors),
            )
        )

        # ---- 2. keyword fallback (weakest) — only when exact found nothing, or on retry
        keyword_anchors: list[_Anchor] = []
        if not anchors or attempt > 0:
            kw = index.keyword_search(claim_text, limit=max(self._kw_anchor_limit, self._max_quran))
            attempts.append(
                RetrievalAttempt(
                    source=TrustedSourceId.QURAN,
                    method=RetrievalMethod.KEYWORD,
                    query_text=claim_text,
                    status=RetrievalAttemptStatus.COMPLETED,
                    candidate_count=len(kw),
                )
            )
            keyword_anchors = [_Anchor(a.ref, RetrievalMatchBasis.KEYWORD) for a, _ in kw]
            kw_scores = {a.quranpedia_ayah_id: s for a, s in kw}
        else:
            kw_scores = {}

        anchor_refs = anchors[: self._max_anchors]
        passage_anchors = anchor_refs or keyword_anchors[: self._kw_anchor_limit]
        if attempt > 0 and anchor_refs:
            passage_anchors = (anchor_refs + keyword_anchors)[: self._max_anchors]

        required = {r.required_claim_type for r in plan.routes}
        for route in plan.routes:
            for sid in route.sources:
                adapter = self._registry.adapter_for(sid)
                if route.required_claim_type == ClaimType.QURAN:
                    q_anchors = anchor_refs + keyword_anchors
                    for a in q_anchors:
                        try:
                            got = await adapter.search(
                                SourceQuery(
                                    source=sid,
                                    method=RetrievalMethod.KEYWORD
                                    if a.basis == RetrievalMatchBasis.KEYWORD
                                    else RetrievalMethod.EXACT,
                                    ayah_refs=[a.ref],
                                    basis=a.basis,
                                )
                            )
                        except MizanError as exc:
                            attempts.append(_failed(sid, RetrievalMethod.EXACT, claim_text, exc))
                            continue
                        for h in got:
                            score = kw_scores.get(a.ref.quranpedia_ayah_id)
                            hits.setdefault(sid, []).append(
                                h.model_copy(update={"score": score}) if score else h
                            )
                    continue
                # tafsir / asbab: live, ayah-anchored
                for a in passage_anchors:
                    query = SourceQuery(
                        source=sid,
                        method=RetrievalMethod.EXACT,
                        query_text=claim_text,
                        anchor=a.ref,
                        basis=a.basis,
                        limit=50,
                    )
                    label = f"anchor {a.ref.surah_number}:{a.ref.ayah_number} ({a.basis.value})"
                    try:
                        got = await adapter.search(query)
                    except MizanError as exc:
                        attempts.append(_failed(sid, RetrievalMethod.EXACT, label, exc))
                        continue
                    attempts.append(
                        RetrievalAttempt(
                            source=sid,
                            method=RetrievalMethod.EXACT,
                            query_text=label,
                            status=RetrievalAttemptStatus.COMPLETED,
                            candidate_count=len(got),
                        )
                    )
                    hits.setdefault(sid, []).extend(got)

        candidates = self._merge_rank(hits)
        strong = any(c.retrieval.match_basis != RetrievalMatchBasis.KEYWORD for c in candidates)
        log.info(
            "retrieval claim types=%s anchors=%d candidates=%d discarded_hints=%d",
            sorted(t.value for t in required),
            len(anchor_refs),
            len(candidates),
            discarded_hints,
        )
        return RetrievalResult(
            claim_id=claim.claim_id,
            candidates=candidates,
            attempts=attempts,
            insufficient_retrieval=not strong,
            anchor_ayahs=[a.ref for a in anchor_refs],
            discarded_hint_count=discarded_hints,
            semantic_search_attempted=False,
        )

    def _merge_rank(self, hits: dict[TrustedSourceId, list[SourceHit]]) -> list[CandidateEvidence]:
        out: list[CandidateEvidence] = []
        for sid, items in hits.items():
            best: dict[str, SourceHit] = {}
            order: dict[str, int] = {}
            for i, h in enumerate(items):
                key = h.evidence.source_record_id or h.evidence.text_sha256
                cur = best.get(key)
                if cur is None or _sort_key(h, i) < _sort_key(cur, order[key]):
                    best[key] = h
                    order[key] = i
            ranked = sorted(best, key=lambda k: _sort_key(best[k], order[k]))
            cap = self._max_quran if sid == TrustedSourceId.QURAN else self._max_passages
            for rank, key in enumerate(ranked[:cap], start=1):
                h = best[key]
                out.append(
                    CandidateEvidence(
                        evidence=h.evidence,
                        retrieval=RetrievalMetadata(
                            retrieval_method=h.method,
                            similarity_score=h.score,
                            retrieval_rank=rank,
                            searched_source=sid,
                            match_basis=h.match_basis,
                            anchor_ayah=h.anchor_ayah,
                        ),
                    )
                )
        return out


def _sort_key(h: SourceHit, arrival: int) -> tuple:
    return (_BASIS_PRIORITY[h.match_basis], -(h.score or 0.0), arrival)


def _failed(
    sid: TrustedSourceId, method: RetrievalMethod, query_text: str, exc: MizanError
) -> RetrievalAttempt:
    info = exc.to_info()
    if info.stage is None:
        info = info.model_copy(update={"stage": PipelineStage.HYBRID_RETRIEVAL})
    return RetrievalAttempt(
        source=sid,
        method=method,
        query_text=query_text,
        status=RetrievalAttemptStatus.FAILED,
        error=info,
    )
