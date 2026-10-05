"""Deterministic Quran verification (Task 5b) — no LLM involved.

Quran evidence establishes ayah WORDING, EXISTENCE and LOCATION only (Source Boundary).
  * Quote component: the quoted words must match the official Mushaf 1 text exactly after
    the matching-only normalisation. Full match -> supports; a run of >= 4 words -> partial;
    nothing -> no assessment (not established). Only strong candidates (quoted text, explicit
    reference, validated hint) are used; keyword-only candidates never count.
  * Location component: a stated surah (and ayah) is compared with where the verified quote
    actually is -> supports, or contradicts with the real verified location.
  * Reference assertion: an explicit surah+ayah reference without any quote (e.g. an ayah
    NAME such as «آية الكرسي هي الآية 255») — the ayah exists, but its text cannot establish
    the assertion -> insufficient (approved decision C).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.claim import ClassifiedClaim
from app.domain.enums import (
    ClaimType,
    ComponentKind,
    EvidenceRelationship,
    ProvidedEvidenceType,
    RetrievalMatchBasis,
)
from app.domain.evidence import AyahRef
from app.domain.retrieval import CandidateEvidence
from app.domain.verification import ClaimComponent, EvidenceAssessment
from app.pipeline.arabic_text import normalize_for_matching
from app.sources.quran_index import MIN_QUOTE_WORDS, QuranIndex

_TOKEN = re.compile(r"\S+")
_QUOTE = re.compile(r"[«﴿﴾“\"]([^«»﴿﴾“”\"]+)[»﴾﴿”\"]")
_EDGE_PUNCT = " \t\n«»﴿﴾“”\"'()[]{}.,،:؛;!؟?"
_AYAH_WORDS = {"الايه", "ايه", "رقم", "الايات", "ايات"}
MIN_SHORT_QUOTE_WORDS = 2
_QUOTE_OK = "النص المقتبس مطابق لنص الآية في المصحف (بعد تطبيع المطابقة فقط)."


@dataclass(frozen=True)
class _Tok:
    norm: str
    start: int
    end: int


@dataclass(frozen=True)
class _StreamWord:
    norm: str
    evidence_id: str


def tokenize(text: str) -> list[_Tok]:
    out: list[_Tok] = []
    for m in _TOKEN.finditer(text):
        for w in normalize_for_matching(m.group()).split():
            out.append(_Tok(w, m.start(), m.end()))
    return out


def _span(text: str, toks: list[_Tok]) -> str:
    return text[toks[0].start : toks[-1].end].strip(_EDGE_PUNCT)


def _streams(cands: list[CandidateEvidence]) -> list[list[_StreamWord]]:
    """Consecutive candidate ayahs of the same surah form one word stream."""
    by_loc = {}
    for c in cands:
        md = c.evidence.metadata
        by_loc[(md.surah_number, md.ayah_number)] = c.evidence
    streams: list[list[_StreamWord]] = []
    prev = None
    for s, a in sorted(by_loc):
        ev = by_loc[(s, a)]
        words = [_StreamWord(w, ev.evidence_id) for w in ev.metadata.ayah_text_normalized.split()]
        if prev == (s, a - 1) and streams:
            streams[-1].extend(words)
        else:
            streams.append(words)
        prev = (s, a)
    return streams


def _longest_run(a: list[str], b: list[str]) -> tuple[int, int, int]:
    """(length, start in a, start in b) of the longest common contiguous run."""
    best = (0, 0, 0)
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best[0]:
                    best = (cur[j], i - cur[j], j - cur[j])
        prev = cur
    return best


@dataclass
class _QuoteResult:
    component: ClaimComponent
    assessments: list[EvidenceAssessment]
    #: evidence id -> matched normalised words in that ayah
    matched: dict[str, str]


class QuranVerifier:
    def __init__(self, index: QuranIndex) -> None:
        self._index = index

    # ------------------------------------------------------------ public

    def verify(
        self, claim: ClassifiedClaim, candidates: list[CandidateEvidence]
    ) -> tuple[list[ClaimComponent], list[EvidenceAssessment]]:
        strong = [
            c
            for c in candidates
            if c.retrieval.match_basis
            in (
                RetrievalMatchBasis.QUOTED_TEXT,
                RetrievalMatchBasis.EXPLICIT_REFERENCE,
                RetrievalMatchBasis.RETRIEVAL_HINT,
            )
        ]
        text = claim.confirmed_claim_text
        self._ref_of = {c.evidence.evidence_id: _ref(c) for c in strong}
        streams = _streams(strong)
        components: list[ClaimComponent] = []
        assessments: list[EvidenceAssessment] = []

        quotes = self._quote_segments(claim)
        results: list[_QuoteResult] = []
        for i, (qtext, qtoks) in enumerate(quotes, start=1):
            r = self._check_quote(f"q{i}", qtext, qtoks, streams, text)
            results.append(r)
        if not quotes:  # implicit quotation of >= 4 consecutive words
            toks = tokenize(text)
            seen: set[tuple[int, int]] = set()
            for stream in streams:
                n, ci, _ = _longest_run([t.norm for t in toks], [w.norm for w in stream])
                if n >= MIN_QUOTE_WORDS and (ci, n) not in seen:
                    seen.add((ci, n))
                    seg = toks[ci : ci + n]
                    cid = f"q{len(results) + 1}"
                    results.append(self._check_quote(cid, _span(text, seg), seg, streams, text))
        for r in results:
            components.append(r.component)
            assessments.extend(r.assessments)

        location = self._stated_location(text)
        if location is not None:
            loc_text, surah, ayah = location
            supported_quotes = [r for r in results if r.matched]
            if supported_quotes:
                c, a = self._check_location("loc1", loc_text, surah, ayah, supported_quotes, strong)
                components.append(c)
                assessments.extend(a)
            elif not results and ayah is not None:
                c, a = self._reference_assertion("ref1", text, surah, ayah, strong)
                components.append(c)
                assessments.extend(a)
            else:
                components.append(
                    ClaimComponent(
                        component_id="loc1",
                        text=loc_text,
                        kind=ComponentKind.QURAN_LOCATION,
                        claim_type=ClaimType.QURAN,
                        detail="لا يمكن التحقق من الموضع لأن النص المقتبس لم يُتحقق منه في المصحف.",
                    )
                )
        if not components:
            components.append(
                ClaimComponent(
                    component_id="q0",
                    text=text.strip(),
                    kind=ComponentKind.QURAN_QUOTE,
                    claim_type=ClaimType.QURAN,
                    detail="لم يُعثر على نص قرآني مطابق أو موضع محدد يمكن التحقق منه.",
                )
            )
        return components, assessments

    # ------------------------------------------------------------ quotes

    def _quote_segments(self, claim: ClassifiedClaim) -> list[tuple[str, list[_Tok]]]:
        text = claim.confirmed_claim_text
        out: list[tuple[str, list[_Tok]]] = []
        for m in _QUOTE.finditer(text):
            seg = m.group(1).strip(_EDGE_PUNCT)
            toks = tokenize(seg)
            if len(toks) >= MIN_SHORT_QUOTE_WORDS:
                out.append((seg, toks))
        pe = claim.provided_evidence
        if pe and pe.provided_evidence_type == ProvidedEvidenceType.QURAN:
            toks = tokenize(pe.provided_evidence_text)
            if len(toks) >= MIN_SHORT_QUOTE_WORDS:
                out.append((pe.provided_evidence_text.strip(), toks))
        return out

    def _check_quote(
        self, cid: str, qtext: str, qtoks: list[_Tok], streams: list[list[_StreamWord]], full: str
    ) -> _QuoteResult:
        words = [t.norm for t in qtoks]
        matched: dict[str, str] = {}
        assessments: list[EvidenceAssessment] = []
        full_hits = []
        best = (0, 0, 0, None)
        for stream in streams:
            n, qi, si = _longest_run(words, [w.norm for w in stream])
            if n == len(words):
                full_hits.append((stream, si, n))
            if n > best[0]:
                best = (n, qi, si, stream)
        if full_hits:
            for stream, si, n in full_hits:
                for ev_id, part in _per_evidence(stream[si : si + n]).items():
                    matched[ev_id] = part
                    assessments.append(
                        EvidenceAssessment(
                            evidence_id=ev_id,
                            relationship=EvidenceRelationship.SUPPORTS,
                            claim_component=qtext,
                            component_id=cid,
                            evidence_span=part,
                            rationale=_QUOTE_OK,
                        )
                    )
        elif best[0] >= MIN_QUOTE_WORDS and best[3] is not None:
            n, qi, si, stream = best
            # Both parts are the user's own wording: verbatim slices of the quote (the match
            # itself is unchanged — it is computed on the normalised words above).
            supported = qtext[qtoks[qi].start : qtoks[qi + n - 1].end].strip()
            before = qtext[: qtoks[qi].start].strip(_EDGE_PUNCT + " ")
            after = qtext[qtoks[qi + n - 1].end :].strip(_EDGE_PUNCT + " ")
            unsupported = " … ".join(p for p in (before, after) if p) or " ".join(
                words[:qi] + words[qi + n :]
            )
            for ev_id, part in _per_evidence(stream[si : si + n]).items():
                matched[ev_id] = part
                assessments.append(
                    EvidenceAssessment(
                        evidence_id=ev_id,
                        relationship=EvidenceRelationship.PARTIALLY_SUPPORTS,
                        claim_component=qtext,
                        component_id=cid,
                        evidence_span=part,
                        supported_part=supported,
                        unsupported_part=unsupported,
                        rationale="جزء من النص المقتبس مطابق لنص الآية، والباقي غير موجود فيها.",
                    )
                )
        component = ClaimComponent(
            component_id=cid,
            text=qtext,
            kind=ComponentKind.QURAN_QUOTE,
            claim_type=ClaimType.QURAN,
            evidence_ids=sorted(matched),
            verified_location=self._refs(matched, streams),
        )
        return _QuoteResult(component, assessments, matched)

    def _refs(self, matched: dict[str, str], streams: list[list[_StreamWord]]):  # type: ignore[no-untyped-def]
        refs = [self._ref_of[e] for e in matched if e in self._ref_of]
        return sorted(refs, key=lambda r: (r.surah_number, r.ayah_number))

    # ------------------------------------------------------------ location

    def _stated_location(self, text: str) -> tuple[str, int, int | None] | None:
        toks = tokenize(text)
        norms = [t.norm for t in toks]
        for i, t in enumerate(toks):
            if t.norm == "سوره":
                got = self._index.match_surah_name(norms, i + 1)
                if not got:
                    continue
                surah, j = got
                ayah, end = None, j
                k = j
                while k < len(toks) and k < j + 4:
                    if toks[k].norm.isdigit():
                        ayah, end = int(toks[k].norm), k + 1
                        break
                    if toks[k].norm not in _AYAH_WORDS:
                        break
                    k += 1
                return _span(text, toks[i:end]), surah, ayah
            if t.norm in {"الايه", "ايه"} and i + 1 < len(toks) and toks[i + 1].norm.isdigit():
                j = i + 2
                if (
                    j + 1 < len(toks)
                    and toks[j].norm in {"من", "في"}
                    and toks[j + 1].norm == "سوره"
                ):
                    got = self._index.match_surah_name(norms, j + 2)
                    if got:
                        return _span(text, toks[i : got[1]]), got[0], int(toks[i + 1].norm)
        return None

    def _check_location(self, cid, loc_text, surah, ayah, quotes, strong):  # type: ignore[no-untyped-def]
        verified = [r for q in quotes for r in q.component.verified_location]
        ok = [
            r
            for r in verified
            if r.surah_number == surah and (ayah is None or r.ayah_number == ayah)
        ]
        matched = {k: v for q in quotes for k, v in q.matched.items()}
        assessments: list[EvidenceAssessment] = []
        if ok:
            ok_ids = {r.quranpedia_ayah_id for r in ok}
            for ev_id, part in matched.items():
                if self._ref_of[ev_id].quranpedia_ayah_id in ok_ids:
                    assessments.append(
                        EvidenceAssessment(
                            evidence_id=ev_id,
                            relationship=EvidenceRelationship.SUPPORTS,
                            claim_component=loc_text,
                            component_id=cid,
                            evidence_span=part,
                            rationale="الموضع المذكور مطابق لموضع النص في المصحف.",
                        )
                    )
            detail = None
            refs = ok
        else:
            where = "، ".join(
                f"{self._index.surah_name(r.surah_number)}، الآية {r.ayah_number}" for r in verified
            )
            for ev_id, part in matched.items():
                assessments.append(
                    EvidenceAssessment(
                        evidence_id=ev_id,
                        relationship=EvidenceRelationship.CONTRADICTS,
                        claim_component=loc_text,
                        component_id=cid,
                        evidence_span=part,
                        rationale=f"النص موجود في {where}، وليس في الموضع المذكور في الادعاء.",
                    )
                )
            detail = f"الموضع الصحيح الموثّق: {where}"
            refs = verified
        component = ClaimComponent(
            component_id=cid,
            text=loc_text,
            kind=ComponentKind.QURAN_LOCATION,
            claim_type=ClaimType.QURAN,
            evidence_ids=sorted({a.evidence_id for a in assessments}),
            verified_location=refs,
            detail=detail,
        )
        return component, assessments

    def _reference_assertion(self, cid, text, surah, ayah, strong):  # type: ignore[no-untyped-def]
        target = self._index.get(surah, ayah)
        ev = next(
            (
                c.evidence
                for c in strong
                if target is not None
                and c.evidence.metadata.quranpedia_ayah_id == target.quranpedia_ayah_id
            ),
            None,
        )
        assessments = []
        if ev is not None:
            assessments.append(
                EvidenceAssessment(
                    evidence_id=ev.evidence_id,
                    relationship=EvidenceRelationship.INSUFFICIENT,
                    claim_component=text.strip(),
                    component_id=cid,
                    rationale=(
                        "الآية المشار إليها موجودة في المصحف، لكن نصها لا يثبت ما نُسب إليها في "
                        "الادعاء (مثل اسم الآية)."
                    ),
                )
            )
        component = ClaimComponent(
            component_id=cid,
            text=text.strip(),
            kind=ComponentKind.QURAN_REFERENCE_ASSERTION,
            claim_type=ClaimType.QURAN,
            evidence_ids=[a.evidence_id for a in assessments],
            verified_location=[target.ref] if target and ev else [],
        )
        return component, assessments


def _ref(c: CandidateEvidence) -> AyahRef:
    md = c.evidence.metadata
    return AyahRef(
        surah_number=md.surah_number,
        ayah_number=md.ayah_number,
        quranpedia_ayah_id=md.quranpedia_ayah_id,
    )


def _per_evidence(words: list[_StreamWord]) -> dict[str, str]:
    out: dict[str, list[str]] = {}
    for w in words:
        out.setdefault(w.evidence_id, []).append(w.norm)
    return {k: " ".join(v) for k, v in out.items()}
