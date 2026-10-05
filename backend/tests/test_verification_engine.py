"""Task 5b: verification engine end-to-end with the Mushaf fixture, mocked Quranpedia and a
scripted LLM. No real network. Dorar must never be called."""

from __future__ import annotations

import re
from collections.abc import Callable

import httpx
import pytest

from app.config import Settings
from app.domain.claim import ConfirmedClaim
from app.domain.enums import (
    ClaimType,
    ComponentKind,
    ComponentOutcome,
    SystemErrorCode,
    UserConfirmationStatus,
    ValidationOutcome,
    VerificationStatus,
)
from app.domain.results import (
    OutOfScopeOutcome,
    RequiredSourceUnavailableOutcome,
    SystemErrorOutcome,
    VerificationOutcome,
)
from app.llm.base import LLMProvider, LLMRequest
from app.llm.schemas import (
    AnalysisRelation,
    ClaimComponentDraft,
    ClassificationSuggestion,
    EvidenceAnalysisDraft,
    EvidenceJudgementDraft,
)
from app.pipeline.factory import build_verification_pipeline
from tests.test_task5a_pipeline import SpyDorar, registry

TEXT_2012 = "الله الذي لا يستحق الألوهية إلا هو، الحي الذي لا تأخذه سنة أي: نعاس ولا نوم"
TEXT_136 = "قوله لا تأخذه سنة ولا نوم أي لا يغلبه نعاس ولا نوم"
WAHIDI = "أنزلت هذه الآية في الأنصار، كانوا يحجون لمناة وكانوا يتحرجون أن يطوفوا بين الصفا والمروة"


def passage(book, name, text, ayahs="262"):
    return {
        "book": {"id": book, "name": name, "author": None},
        "content": [{"text": text, "part": "1", "page": 5, "ayahs": ayahs}],
    }


PASSAGES = {
    "/v1/ayah/2/255/book/2012": passage(2012, "التفسير الميسر", TEXT_2012),
    "/v1/ayah/2/255/book/136": passage(136, "تفسير القرآن العظيم", TEXT_136),
    "/v1/ayah/2/158/book/2919": passage(2919, "أسباب نزول القرآن - الواحدي", WAHIDI, ayahs="165"),
    "/v1/ayah/2/158/book/460": passage(
        460, "المحرر", "قال الله تعالى إن الصفا والمروة من شعائر الله", ayahs="165"
    ),
}


def handler(r: httpx.Request) -> httpx.Response:
    body = PASSAGES.get(r.url.path)
    if body is None:
        book = int(r.url.path.rsplit("/", 1)[-1])
        body = {"book": {"id": book, "name": "كتاب"}, "content": []}
    return httpx.Response(200, json=body)


class ScriptedLLM(LLMProvider):
    name = "scripted"

    def __init__(self, classification: ClassificationSuggestion, analysis: Callable | None = None):
        self.classification = classification
        self.analysis = analysis
        self.calls: list[str] = []

    async def generate_structured(self, request: LLMRequest, output_type):
        self.check_output_type(request, output_type)
        self.calls.append(output_type.__name__)
        if output_type is ClassificationSuggestion:
            return self.classification
        assert self.analysis is not None, "no analysis expected"
        return self.analysis(request, len([c for c in self.calls if c == "EvidenceAnalysisDraft"]))


def labels(request: LLMRequest) -> dict[str, str]:
    """label -> source name, parsed from the prompt the verifier built."""
    return dict(re.findall(r"^=== (E\d+) \| (.+) ===$", request.user_content, re.M))


def segment_ids(request: LLMRequest, label: str, phrase: str | None) -> list[str]:
    """Ids of the numbered segment of `label` containing `phrase` (what a model should cite).

    A phrase that is not in the passage yields an id that does not exist (invalid citation).
    """
    if phrase is None:
        return []
    for sid, text in re.findall(rf"^\[({label}\.\d+)\] (.+)$", request.user_content, re.M):
        if phrase in text:
            return [sid]
    return [f"{label}.999"]


def cls(t, *extra, hints=()):
    return ClassificationSuggestion(
        suggested_claim_type=t,
        additional_claim_types=list(extra),
        ayah_hints=list(hints),
        rationale="r",
    )


async def run(text, llm, reg=None, retries=2):
    reg = reg or registry(handler=handler)
    pipe = build_verification_pipeline(Settings(verification_max_retries=retries), llm, reg)
    claim = ConfirmedClaim(
        claim_id="c1",
        confirmed_claim_text=text,
        user_confirmation_status=UserConfirmationStatus.CONFIRMED,
    )
    [outcome] = (await pipe.run_confirmed([claim])).outcomes
    return outcome


def comps(outcome):
    return {c.kind: c for c in outcome.analysis.components}


def assert_traceable(outcome: VerificationOutcome):
    from app.domain.evidence import text_fingerprint

    for ev in outcome.evidence:
        assert ev.source_address and ev.text_sha256 == text_fingerprint(ev.text)
    assert outcome.validation.outcome in (ValidationOutcome.PASS, ValidationOutcome.ABSTAIN)


# ------------------------------------------------------------------ Quran (deterministic)


async def test_quote_with_correct_surah_is_supported():
    llm = ScriptedLLM(cls(ClaimType.QURAN))
    o = await run("قال تعالى في سورة البقرة: «إن الصفا والمروة من شعائر الله»", llm)
    assert isinstance(o, VerificationOutcome) and o.status == VerificationStatus.SUPPORTED
    c = comps(o)
    assert c[ComponentKind.QURAN_QUOTE].outcome == ComponentOutcome.SUPPORTED
    assert c[ComponentKind.QURAN_LOCATION].outcome == ComponentOutcome.SUPPORTED
    assert llm.calls == ["ClassificationSuggestion"]  # Quran is never judged by the LLM
    assert_traceable(o)


async def test_correct_quote_wrong_surah_is_contradicted_with_details_preserved():
    o = await run(
        "قال تعالى في سورة آل عمران: «إن الصفا والمروة من شعائر الله»",
        ScriptedLLM(cls(ClaimType.QURAN)),
    )
    assert o.status == VerificationStatus.CONTRADICTED
    c = comps(o)
    assert c[ComponentKind.QURAN_QUOTE].outcome == ComponentOutcome.SUPPORTED  # text was right
    loc = c[ComponentKind.QURAN_LOCATION]
    assert loc.outcome == ComponentOutcome.CONTRADICTED and loc.text == "سورة آل عمران"
    assert [(r.surah_number, r.ayah_number) for r in loc.verified_location] == [(2, 158)]
    assert "سورة البقرة، الآية 158" in loc.detail
    assert_traceable(o)


async def test_fabricated_quote_is_no_evidence_not_contradiction():
    o = await run(
        "قال تعالى: «وتعاونوا على الخير ففي ذلك الفلاح المبين»", ScriptedLLM(cls(ClaimType.QURAN))
    )
    assert o.status == VerificationStatus.NO_EVIDENCE_FOUND
    assert all(c.outcome == ComponentOutcome.NOT_ESTABLISHED for c in o.analysis.components)


async def test_keyword_only_candidates_never_count_and_never_reach_the_llm():
    llm = ScriptedLLM(cls(ClaimType.QURAN))
    o = await run("في القرآن أن الحي القيوم لا يأخذه نوم ولا نعاس", llm)
    assert o.status == VerificationStatus.NO_EVIDENCE_FOUND
    assert o.analysis.related_unverified_addresses  # kept as related/unverified only
    assert o.analysis.assessments == [] and o.evidence == []
    assert o.validation.outcome == ValidationOutcome.ABSTAIN  # weak retrieval, evidentiary
    assert llm.calls == ["ClassificationSuggestion"]


async def test_partial_quote_is_partially_supported():
    o = await run(
        "قال تعالى: «إن الصفا والمروة من شعائر الله والصبر مفتاح الفرج»",
        ScriptedLLM(cls(ClaimType.QURAN)),
    )
    assert o.status == VerificationStatus.PARTIALLY_SUPPORTED
    [a] = o.analysis.assessments
    assert a.supported_part and a.unsupported_part


async def test_ayah_name_claim_is_insufficient():
    o = await run("آية الكرسي هي الآية 255 من سورة البقرة", ScriptedLLM(cls(ClaimType.QURAN)))
    assert o.status == VerificationStatus.INSUFFICIENT_EVIDENCE
    assert (
        comps(o)[ComponentKind.QURAN_REFERENCE_ASSERTION].outcome == ComponentOutcome.INSUFFICIENT
    )


async def test_implicit_quote_without_marks():
    o = await run("إن الصفا والمروة من شعائر الله آية من القرآن", ScriptedLLM(cls(ClaimType.QURAN)))
    assert o.status == VerificationStatus.SUPPORTED


# ------------------------------------------------------------------ tafsir / asbab (validated LLM)


def analysis_for(
    judge: Callable[[str, str], tuple] | None, component="لا يأخذه نعاس", ctype=ClaimType.TAFSIR
):
    def fn(request, n):
        js = []
        for label, source in labels(request).items():
            rel, span = judge(label, source)
            js.append(
                EvidenceJudgementDraft(
                    item=label,
                    component_id="c1",
                    relation=rel,
                    segments=segment_ids(request, label, span),
                    rationale="r",
                )
            )
        return EvidenceAnalysisDraft(
            components=[ClaimComponentDraft(component_id="c1", text=component, claim_type=ctype)],
            judgements=js,
        )

    return fn


TAFSIR_CLAIM = "معنى «لا تأخذه سنة ولا نوم» أن الله لا يأخذه نعاس"


async def test_tafsir_supported_with_verbatim_span():
    def judge(label, source):
        if "الميسر" in source:
            return AnalysisRelation.SUPPORTS, "لا تأخذه سنة أي: نعاس"
        return AnalysisRelation.INSUFFICIENT, None

    llm = ScriptedLLM(cls(ClaimType.TAFSIR), analysis_for(judge))
    o = await run(TAFSIR_CLAIM, llm)
    assert o.status == VerificationStatus.SUPPORTED
    assert llm.calls.count("EvidenceAnalysisDraft") == 1  # one analysis call per claim
    sup = [a for a in o.analysis.assessments if a.relationship.value == "supports"]
    assert sup and sup[0].assessed_by == "llm_analysis"
    assert_traceable(o)


async def test_tafsir_evidence_conflict():
    def judge(label, source):
        if "الميسر" in source:
            return AnalysisRelation.SUPPORTS, "لا تأخذه سنة أي: نعاس"
        return AnalysisRelation.CONTRADICTS, "لا يغلبه نعاس ولا نوم"

    o = await run(TAFSIR_CLAIM, ScriptedLLM(cls(ClaimType.TAFSIR), analysis_for(judge)))
    assert o.status == VerificationStatus.CONFLICTING_EVIDENCE
    assert o.analysis.evidence_conflicts


async def test_unrelated_passages_give_no_evidence_found():
    o = await run(
        TAFSIR_CLAIM,
        ScriptedLLM(
            cls(ClaimType.TAFSIR), analysis_for(lambda *_: (AnalysisRelation.UNRELATED, None))
        ),
    )
    assert o.status == VerificationStatus.NO_EVIDENCE_FOUND and o.evidence == []


async def test_invalid_span_is_retried_once_then_accepted():
    def fn(request, n):
        span = "نص مخترع غير موجود في المقطع" if n == 1 else "لا تأخذه سنة أي: نعاس"
        label = next(lbl for lbl, src in labels(request).items() if "الميسر" in src)
        return EvidenceAnalysisDraft(
            components=[
                ClaimComponentDraft(
                    component_id="c1", text="لا يأخذه نعاس", claim_type=ClaimType.TAFSIR
                )
            ],
            judgements=[
                EvidenceJudgementDraft(
                    item=label,
                    component_id="c1",
                    relation=AnalysisRelation.SUPPORTS,
                    segments=segment_ids(request, label, span),
                    rationale="r",
                )
            ],
        )

    llm = ScriptedLLM(cls(ClaimType.TAFSIR), fn)
    o = await run(TAFSIR_CLAIM, llm)
    assert (
        o.status == VerificationStatus.SUPPORTED and llm.calls.count("EvidenceAnalysisDraft") == 2
    )


@pytest.mark.parametrize(
    "judge,component,ctype",
    [
        (
            lambda *_: (AnalysisRelation.SUPPORTS, "نص مخترع غير موجود"),
            "لا يأخذه نعاس",
            ClaimType.TAFSIR,
        ),
        (lambda *_: (AnalysisRelation.SUPPORTS, None), "لا يأخذه نعاس", ClaimType.TAFSIR),
        (
            lambda *_: (AnalysisRelation.INSUFFICIENT, None),
            "عبارة ليست في الادعاء",
            ClaimType.TAFSIR,
        ),
        (lambda *_: (AnalysisRelation.INSUFFICIENT, None), "لا يأخذه نعاس", ClaimType.ASBAB_NUZUL),
    ],
)
async def test_invalid_analysis_fails_closed_as_system_error_not_a_status(judge, component, ctype):
    o = await run(
        TAFSIR_CLAIM, ScriptedLLM(cls(ClaimType.TAFSIR), analysis_for(judge, component, ctype))
    )
    assert isinstance(o, SystemErrorOutcome)
    assert o.error.code == SystemErrorCode.VERIFICATION_INCOMPLETE
    assert not hasattr(o, "status")


async def test_asbab_supported_relation_type_stays_unspecified():
    def judge(label, source):
        if "واحدي" in source:
            return AnalysisRelation.SUPPORTS, "أنزلت هذه الآية في الأنصار"
        return AnalysisRelation.INSUFFICIENT, None

    claim = "نزل قوله تعالى «إن الصفا والمروة من شعائر الله» في الأنصار"
    o = await run(
        claim,
        ScriptedLLM(
            cls(ClaimType.ASBAB_NUZUL), analysis_for(judge, "في الأنصار", ClaimType.ASBAB_NUZUL)
        ),
    )
    assert o.status == VerificationStatus.SUPPORTED
    for ev in o.evidence:
        assert ev.metadata.relation_type.value == "unspecified"


async def test_wrong_tafsir_meaning_is_contradicted_never_supported():
    def judge(label, source):
        if "الميسر" in source:
            return AnalysisRelation.CONTRADICTS, "لا تأخذه سنة أي: نعاس"
        return AnalysisRelation.INSUFFICIENT, None

    o = await run(TAFSIR_CLAIM, ScriptedLLM(cls(ClaimType.TAFSIR), analysis_for(judge)))
    assert o.status == VerificationStatus.CONTRADICTED
    assert_traceable(o)


async def test_wrong_asbab_event_is_contradicted_with_the_real_text_cited():
    def judge(label, source):
        if "واحدي" in source:
            return AnalysisRelation.CONTRADICTS, "أنزلت هذه الآية في الأنصار"
        return AnalysisRelation.INSUFFICIENT, None

    claim = "نزل قوله تعالى «إن الصفا والمروة من شعائر الله» في غزوة بدر"
    o = await run(
        claim,
        ScriptedLLM(
            cls(ClaimType.ASBAB_NUZUL), analysis_for(judge, "في غزوة بدر", ClaimType.ASBAB_NUZUL)
        ),
    )
    assert o.status == VerificationStatus.CONTRADICTED
    cited = [a for a in o.analysis.assessments if a.relationship.value == "contradicts"]
    assert cited
    for a in cited:
        ev = next(e for e in o.evidence if e.evidence_id == a.evidence_id)
        assert a.evidence_span in ev.text  # the displayed span is real source text
    assert_traceable(o)


async def test_wrong_asbab_with_only_related_text_is_not_supported():
    claim = "نزل قوله تعالى «إن الصفا والمروة من شعائر الله» في غزوة بدر"
    o = await run(
        claim,
        ScriptedLLM(
            cls(ClaimType.ASBAB_NUZUL),
            analysis_for(
                lambda *_: (AnalysisRelation.INSUFFICIENT, None),
                "في غزوة بدر",
                ClaimType.ASBAB_NUZUL,
            ),
        ),
    )
    assert o.status in {
        VerificationStatus.INSUFFICIENT_EVIDENCE,
        VerificationStatus.NO_EVIDENCE_FOUND,
    }


async def test_quran_plus_tafsir_claim_keeps_source_boundary():
    def judge(label, source):
        return (
            (AnalysisRelation.SUPPORTS, "لا تأخذه سنة أي: نعاس")
            if "الميسر" in source
            else (AnalysisRelation.INSUFFICIENT, None)
        )

    o = await run(
        TAFSIR_CLAIM, ScriptedLLM(cls(ClaimType.TAFSIR, ClaimType.QURAN), analysis_for(judge))
    )
    assert o.status == VerificationStatus.SUPPORTED
    for a in o.analysis.assessments:
        comp = next(c for c in o.analysis.components if c.component_id == a.component_id)
        src_type = next(e for e in o.evidence if e.evidence_id == a.evidence_id).source_type.value
        assert (
            src_type == comp.claim_type.value
        )  # each component judged only by its own source type


# ------------------------------------------------------------------ abstentions / failures


async def test_hadith_abstains_and_nothing_is_verified():
    llm = ScriptedLLM(cls(ClaimType.HADITH))
    o = await run("قال رسول الله ﷺ: «إنما الأعمال بالنيات»", llm)
    assert isinstance(o, RequiredSourceUnavailableOutcome) and not hasattr(o, "status")
    assert llm.calls == ["ClassificationSuggestion"]


async def test_out_of_scope():
    o = await run("صيام يوم الاثنين واجب", ScriptedLLM(cls(None)))
    assert isinstance(o, OutOfScopeOutcome)


async def test_source_failure_fails_closed_after_bounded_retries_without_analysis():
    calls = {"n": 0}

    def failing(r):
        calls["n"] += 1
        return httpx.Response(503)

    llm = ScriptedLLM(
        cls(ClaimType.TAFSIR), analysis_for(lambda *_: (AnalysisRelation.INSUFFICIENT, None))
    )
    o = await run(TAFSIR_CLAIM, llm, reg=registry(handler=failing), retries=1)
    assert (
        isinstance(o, SystemErrorOutcome)
        and o.error.code == SystemErrorCode.VERIFICATION_INCOMPLETE
    )
    assert "EvidenceAnalysisDraft" not in llm.calls  # never analysed on partial data
    assert calls["n"] > 2  # the bounded retry really re-queried the sources


async def test_integrity_failure_after_retries_is_system_error(monkeypatch):
    from app.pipeline import gate as gate_mod

    monkeypatch.setattr(gate_mod, "text_fingerprint", lambda text: "0" * 64)  # simulate corruption
    o = await run(
        "قال تعالى في سورة البقرة: «إن الصفا والمروة من شعائر الله»",
        ScriptedLLM(cls(ClaimType.QURAN)),
    )
    assert isinstance(o, SystemErrorOutcome)
    assert (
        o.error.code == SystemErrorCode.VERIFICATION_INCOMPLETE
        and "integrity_failure" in o.error.message
    )


def test_dorar_spy_is_registered():
    reg = registry(handler=handler)
    assert any(isinstance(a, SpyDorar) for a in reg.adapters())


# ------------------------------------------------------------------ regression: anchors (fix 2)


def by_role(o):
    return {c.role.value: c for c in o.analysis.components}


async def test_valid_quran_anchor_does_not_inflate_tafsir_status():
    """Real smoke case 6: verified quote + unestablished meaning must NOT be partially_supported."""
    claim = "معنى قوله تعالى «لا تأخذه سنة ولا نوم» أن الله لا يغضب على عباده"
    llm = ScriptedLLM(
        cls(ClaimType.TAFSIR, ClaimType.QURAN),
        analysis_for(lambda *_: (AnalysisRelation.INSUFFICIENT, None), "أن الله لا يغضب على عباده"),
    )
    o = await run(claim, llm)
    assert o.status == VerificationStatus.INSUFFICIENT_EVIDENCE
    anchor = next(c for c in o.analysis.components if c.kind == ComponentKind.QURAN_QUOTE)
    assert (
        anchor.role.value == "anchor" and anchor.outcome == ComponentOutcome.SUPPORTED
    )  # kept & shown
    assert by_role(o)["substantive"].outcome == ComponentOutcome.INSUFFICIENT


async def test_valid_anchor_with_unrelated_passages_is_no_evidence_found():
    o = await run(
        TAFSIR_CLAIM,
        ScriptedLLM(
            cls(ClaimType.TAFSIR, ClaimType.QURAN),
            analysis_for(lambda *_: (AnalysisRelation.UNRELATED, None)),
        ),
    )
    assert o.status == VerificationStatus.NO_EVIDENCE_FOUND


async def test_supported_asbab_with_anchor_stays_supported():
    def judge(label, source):
        return (
            (AnalysisRelation.SUPPORTS, "أنزلت هذه الآية في الأنصار")
            if "واحدي" in source
            else (AnalysisRelation.INSUFFICIENT, None)
        )

    claim = "نزل قوله تعالى «إن الصفا والمروة من شعائر الله» في الأنصار"
    o = await run(
        claim,
        ScriptedLLM(
            cls(ClaimType.ASBAB_NUZUL, ClaimType.QURAN),
            analysis_for(judge, "في الأنصار", ClaimType.ASBAB_NUZUL),
        ),
    )
    assert o.status == VerificationStatus.SUPPORTED


async def test_partial_asbab_comes_from_substantive_components():
    claim = (
        "نزل قوله تعالى «إن الصفا والمروة من شعائر الله» في الأنصار، "
        "وكان ذلك في السنة الأولى من الهجرة"
    )

    def fn(request, n):
        wahidi = next(lbl for lbl, src in labels(request).items() if "واحدي" in src)
        return EvidenceAnalysisDraft(
            components=[
                ClaimComponentDraft(
                    component_id="c1", text="في الأنصار", claim_type=ClaimType.ASBAB_NUZUL
                ),
                ClaimComponentDraft(
                    component_id="c2",
                    text="وكان ذلك في السنة الأولى من الهجرة",
                    claim_type=ClaimType.ASBAB_NUZUL,
                ),
            ],
            judgements=[
                EvidenceJudgementDraft(
                    item=wahidi,
                    component_id="c1",
                    relation=AnalysisRelation.SUPPORTS,
                    segments=segment_ids(request, wahidi, "أنزلت هذه الآية في الأنصار"),
                    rationale="r",
                ),
                EvidenceJudgementDraft(
                    item=wahidi,
                    component_id="c2",
                    relation=AnalysisRelation.UNRELATED,
                    rationale="r",
                ),
            ],
        )

    o = await run(claim, ScriptedLLM(cls(ClaimType.ASBAB_NUZUL, ClaimType.QURAN), fn))
    assert o.status == VerificationStatus.PARTIALLY_SUPPORTED


async def test_contradicted_anchor_still_makes_the_claim_contradicted():
    def judge(label, source):
        return (
            (AnalysisRelation.SUPPORTS, "لا تأخذه سنة أي: نعاس")
            if "الميسر" in source
            else (AnalysisRelation.INSUFFICIENT, None)
        )

    claim = "معنى قوله تعالى في سورة آل عمران «لا تأخذه سنة ولا نوم» أن الله لا يأخذه نعاس"
    o = await run(claim, ScriptedLLM(cls(ClaimType.TAFSIR, ClaimType.QURAN), analysis_for(judge)))
    assert o.status == VerificationStatus.CONTRADICTED
    loc = next(c for c in o.analysis.components if c.kind == ComponentKind.QURAN_LOCATION)
    assert loc.role.value == "anchor" and loc.outcome == ComponentOutcome.CONTRADICTED


async def test_pure_quran_claim_components_are_substantive():
    o = await run(
        "قال تعالى في سورة البقرة: «إن الصفا والمروة من شعائر الله»",
        ScriptedLLM(cls(ClaimType.QURAN)),
    )
    assert {c.role.value for c in o.analysis.components} == {"substantive"}


# ------------------------------------------------------------------ regression: spans (fix 1)


def test_segments_are_exact_substrings_of_the_evidence():
    from app.pipeline.passage_analysis import segment_passage

    text = (
        "قوله تعالى: لا تأخذه سنة.\nأي لا يغلبه نعاس ولا نوم؛ " + " ".join(["كلمة"] * 70) + " نهاية"
    )
    segs = segment_passage(text)
    assert len(segs) >= 4
    for a, b in segs:
        assert text[a:b] and text[a:b] == text[a:b].strip()
    assert all(len(text[a:b].split()) <= 30 for a, b in segs)


async def test_multi_segment_citation_yields_one_exact_contiguous_span():
    long_text = "أول جملة في المقطع هنا. ثاني جملة تقول لا يأخذه نعاس. ثالث جملة للختام هنا."
    PASSAGES_LONG = dict(PASSAGES)
    PASSAGES_LONG["/v1/ayah/2/255/book/2012"] = passage(2012, "التفسير الميسر", long_text)

    def h(r):
        body = PASSAGES_LONG.get(r.url.path) or {
            "book": {"id": int(r.url.path.rsplit("/", 1)[-1]), "name": "x"},
            "content": [],
        }
        return httpx.Response(200, json=body)

    def fn(request, n):
        lbl = next(x for x, src in labels(request).items() if "الميسر" in src)
        return EvidenceAnalysisDraft(
            components=[
                ClaimComponentDraft(
                    component_id="c1", text="لا يأخذه نعاس", claim_type=ClaimType.TAFSIR
                )
            ],
            judgements=[
                EvidenceJudgementDraft(
                    item=lbl,
                    component_id="c1",
                    relation=AnalysisRelation.SUPPORTS,
                    segments=[f"{lbl}.2", f"{lbl}.3"],
                    rationale="r",
                )
            ],
        )

    o = await run(TAFSIR_CLAIM, ScriptedLLM(cls(ClaimType.TAFSIR), fn), reg=registry(handler=h))
    [a] = [x for x in o.analysis.assessments if x.relationship.value == "supports"]
    assert a.evidence_span == "ثاني جملة تقول لا يأخذه نعاس. ثالث جملة للختام هنا."
    assert a.evidence_span in long_text  # byte-exact substring of the source text


@pytest.mark.parametrize(
    "cite",
    [
        lambda lbl, other: [f"{lbl}.1", f"{lbl}.3"],
        lambda lbl, other: [f"{other}.1"],
        lambda lbl, other: [],
    ],
)
async def test_bad_segment_citations_fail_closed(cite):
    def fn(request, n):
        ls = list(labels(request))
        lbl = next(x for x, src in labels(request).items() if "الميسر" in src)
        other = next(x for x in ls if x != lbl)
        return EvidenceAnalysisDraft(
            components=[
                ClaimComponentDraft(
                    component_id="c1", text="لا يأخذه نعاس", claim_type=ClaimType.TAFSIR
                )
            ],
            judgements=[
                EvidenceJudgementDraft(
                    item=lbl,
                    component_id="c1",
                    relation=AnalysisRelation.SUPPORTS,
                    segments=cite(lbl, other),
                    rationale="r",
                )
            ],
        )

    llm = ScriptedLLM(cls(ClaimType.TAFSIR), fn)
    o = await run(TAFSIR_CLAIM, llm)
    assert (
        isinstance(o, SystemErrorOutcome)
        and o.error.code == SystemErrorCode.VERIFICATION_INCOMPLETE
    )
    assert llm.calls.count("EvidenceAnalysisDraft") == 2  # one allowed retry, then fail closed
