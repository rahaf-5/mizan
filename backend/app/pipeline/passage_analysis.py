"""Gemini analysis of retrieved tafsir / asbab passages (Task 5b) — validated, fail-closed.

Gemini only RELATES given passages to verbatim components of the confirmed claim. Mizan then:
  * rejects components that are not verbatim spans of the claim;
  * rejects supports / partially_supports / contradicts without a verbatim span (>= 3 words)
    that really occurs in that passage's text;
  * drops `unrelated` judgements and judgements that cross the Source Boundary.
An invalid analysis is re-requested ONCE; if still invalid, verification fails closed
(VerificationIntegrityError -> system error, never an evidentiary status).
"""

from __future__ import annotations

from app.core_logging import get_logger
from app.domain.claim import ClassifiedClaim
from app.domain.enums import ClaimType, ComponentKind, EvidenceRelationship, PipelineStage
from app.domain.errors import VerificationIntegrityError
from app.domain.retrieval import CandidateEvidence
from app.domain.trusted_sources import get_trusted_source
from app.domain.verification import ClaimComponent, EvidenceAssessment
from app.llm.base import LLMProvider, LLMRequest
from app.llm.prompts.evidence_analysis import build_prompt
from app.llm.schemas import AnalysisRelation, EvidenceAnalysisDraft, LLMTask
from app.pipeline.arabic_text import normalize_for_matching

log = get_logger("pipeline.passage_analysis")
MAX_PASSAGE_CHARS = 6000
MIN_SPAN_WORDS = 3
_REL = {
    AnalysisRelation.SUPPORTS: EvidenceRelationship.SUPPORTS,
    AnalysisRelation.PARTIALLY_SUPPORTS: EvidenceRelationship.PARTIALLY_SUPPORTS,
    AnalysisRelation.CONTRADICTS: EvidenceRelationship.CONTRADICTS,
    AnalysisRelation.INSUFFICIENT: EvidenceRelationship.INSUFFICIENT,
}


def occurs_in(span: str, text: str, *, min_words: int = MIN_SPAN_WORDS) -> bool:
    """Exact (normalised) occurrence of `span` in `text` — no fuzzy matching."""
    s = normalize_for_matching(span)
    return len(s.split()) >= min_words and f" {s} " in f" {normalize_for_matching(text)} "


def is_claim_span(component: str, claim_text: str) -> bool:
    c = normalize_for_matching(component)
    return bool(c) and f" {c} " in f" {normalize_for_matching(claim_text)} "


class PassageAnalyzer:
    def __init__(self, provider: LLMProvider, *, max_attempts: int = 2) -> None:
        self._provider = provider
        self._max_attempts = max_attempts

    async def analyze(
        self,
        claim: ClassifiedClaim,
        passages: list[CandidateEvidence],
        types: list[ClaimType],
    ) -> tuple[list[ClaimComponent], list[EvidenceAssessment]]:
        labels = {f"E{i}": c for i, c in enumerate(passages, start=1)}
        items = [
            (label, c.evidence.source_name, c.evidence.text[:MAX_PASSAGE_CHARS])
            for label, c in labels.items()
        ]
        system, user = build_prompt(claim.confirmed_claim_text, items, [t.value for t in types])
        problems: list[str] = []
        for attempt in range(1, self._max_attempts + 1):
            content = user
            if problems:
                content += "\n\n[تصحيح مطلوب] الإجابة السابقة غير صالحة: " + "؛ ".join(problems[:5])
            draft = await self._provider.generate_structured(
                LLMRequest(
                    task=LLMTask.CONSTRAINED_EVIDENCE_ANALYSIS,
                    system_prompt=system,
                    user_content=content,
                ),
                EvidenceAnalysisDraft,
            )
            problems = self._problems(draft, claim, labels, types)
            if not problems:
                return self._convert(draft, labels, types)
            log.warning("invalid evidence analysis (attempt %d): %s", attempt, problems[:3])
        raise VerificationIntegrityError(
            "evidence analysis invalid after retry: " + "; ".join(problems[:3]),
            stage=PipelineStage.EVIDENCE_VERIFICATION,
        )

    # ------------------------------------------------------------ validation

    def _problems(self, draft, claim, labels, types) -> list[str]:  # type: ignore[no-untyped-def]
        out: list[str] = []
        if not draft.components:
            out.append("no components")
        ids = [c.component_id for c in draft.components]
        if len(set(ids)) != len(ids):
            out.append("duplicate component ids")
        for comp in draft.components:
            if not is_claim_span(comp.text, claim.confirmed_claim_text):
                out.append(f"component {comp.component_id} is not a verbatim span of the claim")
            if comp.claim_type not in types:
                out.append(f"component {comp.component_id} has a type outside {types}")
        for j in draft.judgements:
            if j.item not in labels:
                out.append(f"unknown passage {j.item}")
                continue
            if j.component_id not in ids:
                out.append(f"unknown component {j.component_id}")
                continue
            if j.relation in (
                AnalysisRelation.SUPPORTS,
                AnalysisRelation.PARTIALLY_SUPPORTS,
                AnalysisRelation.CONTRADICTS,
            ):
                if not j.span or not occurs_in(j.span, labels[j.item].evidence.text):
                    out.append(f"{j.item}/{j.component_id}: span not found verbatim in passage")
            if j.relation == AnalysisRelation.PARTIALLY_SUPPORTS and not (
                j.supported_part and j.unsupported_part
            ):
                out.append(f"{j.item}/{j.component_id}: partial without both parts")
        return out

    def _convert(self, draft, labels, types):  # type: ignore[no-untyped-def]
        cid = {c.component_id: f"s{i}" for i, c in enumerate(draft.components, start=1)}
        ctype = {c.component_id: c.claim_type for c in draft.components}
        ctext = {c.component_id: c.text.strip() for c in draft.components}
        assessments: list[EvidenceAssessment] = []
        seen: set[tuple[str, str]] = set()
        for j in draft.judgements:
            if j.relation == AnalysisRelation.UNRELATED:
                continue
            cand = labels[j.item]
            key = (cand.evidence.evidence_id, j.component_id)
            if key in seen:
                continue
            seen.add(key)
            src = get_trusted_source(cand.evidence.trusted_source_id)
            if ctype[j.component_id] not in src.qualified_for:
                continue  # Source Boundary: this source cannot establish this component
            rel = _REL[j.relation]
            span = j.span.strip() if j.span else None
            if (
                rel == EvidenceRelationship.INSUFFICIENT
                and span
                and not occurs_in(span, cand.evidence.text, min_words=1)
            ):
                span = None  # optional for insufficient; never keep an unverifiable span
            assessments.append(
                EvidenceAssessment(
                    evidence_id=cand.evidence.evidence_id,
                    relationship=rel,
                    claim_component=ctext[j.component_id],
                    component_id=cid[j.component_id],
                    evidence_span=span,
                    supported_part=j.supported_part,
                    unsupported_part=j.unsupported_part,
                    rationale=j.rationale.strip(),
                    assessed_by="llm_analysis",
                )
            )
        components = [
            ClaimComponent(
                component_id=cid[c.component_id],
                text=ctext[c.component_id],
                kind=ComponentKind.STATEMENT,
                claim_type=c.claim_type,
                evidence_ids=sorted(
                    {a.evidence_id for a in assessments if a.component_id == cid[c.component_id]}
                ),
            )
            for c in draft.components
        ]
        return components, assessments
