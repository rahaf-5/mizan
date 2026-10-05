"""Evidence Verification (Task 5b).

Each qualified candidate is judged independently against verbatim components of the confirmed
claim:
  * Quran components — deterministic (`quran_checks.QuranVerifier`), no LLM;
  * tafsir / asbab components — Gemini constrained analysis of the top passages
    (max 3 per source, one analysis call per claim), validated by `PassageAnalyzer`.
Keyword-only candidates are NEVER judged: they are kept only as related/unverified addresses.
"""

from __future__ import annotations

import re

from app.domain.claim import ClassifiedClaim
from app.domain.enums import ClaimType, ComponentKind, ComponentRole, RetrievalMatchBasis
from app.domain.retrieval import CandidateEvidence
from app.domain.trusted_sources import TrustedSourceId, get_trusted_source
from app.domain.verification import ClaimComponent, EvidenceAssessment, VerificationFindings
from app.llm.base import LLMProvider
from app.pipeline.arabic_text import normalize_for_matching
from app.pipeline.passage_analysis import PassageAnalyzer
from app.pipeline.quran_checks import QuranVerifier
from app.sources.registry import AdapterRegistry

PASSAGE_TYPES = (ClaimType.TAFSIR, ClaimType.ASBAB_NUZUL)

#: A part of the claim left out of every component must never be silently dropped: a run of
#: uncovered words with at least this many content words becomes its own component, which no
#: evidence judged (-> not established). Framing words alone (e.g. «معنى قوله تعالى») do not count.
MIN_UNCOVERED_CONTENT_WORDS = 3
_FRAMING_WORDS = frozenset(
    normalize_for_matching(w)
    for w in (
        "و في من على إلى عن أن إن ان كان وكان ذلك هذا هذه الذي التي ثم "
        "قال وقال قوله تعالى سبحانه عز وجل نزل نزلت معنى تفسير الآية آية سورة"
    ).split()
)
_TOKEN = re.compile(r"\S+")
#: A quotation inside a tafsir / asbab claim names the ayah it is about (its subject), it is not
#: a separate assertion; Quran quotes are verified by their own (anchor) components.
_QUOTED = re.compile(r"«[^»]*»|\"[^\"]*\"|“[^”]*”")


def uncovered_parts(text: str, components: list[ClaimComponent]) -> list[str]:
    """Verbatim parts of `text` that no component covers and that carry real content."""
    toks = [(m.start(), m.end(), normalize_for_matching(m.group())) for m in _TOKEN.finditer(text)]
    # normalised words, each mapped back to the raw token it came from
    words: list[str] = []
    owner: list[int] = []
    for k, (_, _, norm) in enumerate(toks):
        for w in norm.split():
            words.append(w)
            owner.append(k)
    quoted = [(m.start(), m.end()) for m in _QUOTED.finditer(text)]
    # pure punctuation and quoted text need no coverage
    covered = [not norm or any(a <= s < b for a, b in quoted) for s, _, norm in toks]
    for comp in components:
        cw = normalize_for_matching(comp.text).split()
        n = len(cw)
        for i in range(len(words) - n + 1) if n else ():
            if words[i : i + n] == cw:
                for k in range(i, i + n):
                    covered[owner[k]] = True
    parts: list[str] = []
    i = 0
    while i < len(toks):
        if covered[i]:
            i += 1
            continue
        j = i
        while j < len(toks) and not covered[j]:
            j += 1
        run = toks[i:j]
        content = [w for _, _, norm in run for w in norm.split() if w not in _FRAMING_WORDS]
        if len(content) >= MIN_UNCOVERED_CONTENT_WORDS:
            part = text[run[0][0] : run[-1][1]].strip(" \t\n،,.;؛:!?؟")
            if part:
                parts.append(part)
        i = j
    return parts


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
                for i, part in enumerate(
                    uncovered_parts(claim.confirmed_claim_text, components), start=1
                ):
                    components.append(
                        ClaimComponent(
                            component_id=f"u{i}",
                            text=part,
                            kind=ComponentKind.STATEMENT,
                            claim_type=types[0],
                            detail="هذا الجزء من الادعاء لم يُقابَل بأي دليل من المصادر المعتمدة.",
                        )
                    )
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
