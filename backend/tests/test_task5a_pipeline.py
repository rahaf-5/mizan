"""Task 5a: classification -> deterministic routing -> retrieval (no verdicts).

LLM and HTTP are mocked. Dorar must never be called.
"""

from __future__ import annotations

import httpx
import pytest

from app.domain.claim import (
    AyahRetrievalHint,
    Claim,
    ClassifiedClaim,
    ConfirmedClaim,
    ProvidedEvidence,
)
from app.domain.enums import (
    ClaimType,
    ProvidedEvidenceType,
    RetrievalAttemptStatus,
    RetrievalMatchBasis,
    UserConfirmationStatus,
)
from app.domain.errors import LLMRateLimitedError
from app.domain.results import OutOfScopeOutcome, RequiredSourceUnavailableOutcome
from app.domain.routing import SourceRoutingPlan
from app.domain.trusted_sources import TrustedSourceId as T
from app.llm.fake import FakeLLMProvider
from app.llm.schemas import AyahHintDraft, ClassificationSuggestion
from app.pipeline import stubs
from app.pipeline.classification import LlmClaimClassifier, hadith_signal
from app.pipeline.orchestrator import PipelineStages, VerificationPipeline
from app.pipeline.retrieval import TrustedSourceRetriever
from app.pipeline.routing import DeterministicSourceRouter
from app.sources.dorar import DorarAdapter
from app.sources.quran_index import QuranDataMissingError
from app.sources.quranpedia import QuranpediaAdapter
from app.sources.registry import AdapterRegistry
from tests.quran_fixture import gid, make_index
from tests.test_quranpedia_adapter import RESPONSES

INDEX = make_index()


class SpyDorar(DorarAdapter):
    async def search(self, query):  # pragma: no cover - must never run
        raise AssertionError("Dorar must never be called while it is unavailable")

    async def get_records(self, source, source_address):  # pragma: no cover
        raise AssertionError("Dorar must never be called while it is unavailable")


def registry(handler=None, *, quranpedia_enabled=True, dorar_enabled=True, index=INDEX, seen=None):
    def default(r: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(r.url.path)
        body = RESPONSES.get(r.url.path)
        if body is None:
            book_id = int(r.url.path.rsplit("/", 1)[-1])
            body = {"book": {"id": book_id, "name": "كتاب"}, "content": []}
        return httpx.Response(200, json=body)

    reg = AdapterRegistry()
    reg.register(
        QuranpediaAdapter(
            enabled=quranpedia_enabled,
            quran_index=index,
            transport=httpx.MockTransport(handler or default),
        )
    )
    reg.register(SpyDorar(enabled=dorar_enabled))  # config cannot override policy
    return reg


def classified(text, claim_type, *, extra=(), hints=(), provided=None, ref=None):
    return ClassifiedClaim(
        claim_id="c1",
        confirmed_claim_text=text,
        user_confirmation_status=UserConfirmationStatus.CONFIRMED,
        claim_type=claim_type,
        additional_claim_types=list(extra),
        retrieval_hints=list(hints),
        provided_evidence=provided,
        provided_reference=ref,
    )


def confirmed(text, **kw):
    return ConfirmedClaim(
        claim_id="c1",
        confirmed_claim_text=text,
        user_confirmation_status=UserConfirmationStatus.CONFIRMED,
        **kw,
    )


# ------------------------------------------------------------------ classification


async def test_classifier_passes_types_and_hints_without_validating_them():
    llm = FakeLLMProvider(
        [
            ClassificationSuggestion(
                suggested_claim_type=ClaimType.TAFSIR,
                additional_claim_types=[ClaimType.QURAN],
                ayah_hints=[
                    AyahHintDraft(surah_number=2, ayah_start=255),
                    AyahHintDraft(surah_number=900, ayah_start=1),
                ],
                rationale="r",
            )
        ]
    )
    out = await LlmClaimClassifier(llm).classify(confirmed("معنى «لا تأخذه سنة» في آية الكرسي"))
    assert out.required_claim_types == [ClaimType.TAFSIR, ClaimType.QURAN]
    assert [(h.surah_number, h.ayah_start) for h in out.retrieval_hints] == [(2, 255), (900, 1)]
    assert "<<<CLAIM-" in llm.requests[0].user_content  # untrusted-data boundary


@pytest.mark.parametrize(
    "text,expected",
    [
        ("قال رسول الله ﷺ: «إنما الأعمال بالنيات»", True),
        ("عن النبي صلى الله عليه وسلم قال: الصبر ضياء", True),
        ("نزلت هذه الآية في الأنصار حين سألوا النبي ﷺ", False),  # asbab narration
        ("آية الكرسي في سورة البقرة", False),
    ],
)
def test_hadith_signal_is_narrow(text, expected):
    assert hadith_signal(text) is expected


async def test_hadith_marker_forces_hadith_requirement_even_if_llm_misses_it():
    llm = FakeLLMProvider(
        [ClassificationSuggestion(suggested_claim_type=ClaimType.QURAN, rationale="r")]
    )
    out = await LlmClaimClassifier(llm).classify(
        confirmed("«إن الله مع الصابرين» آية، وقال النبي ﷺ: الصبر ضياء")
    )
    assert out.required_claim_types == [ClaimType.QURAN, ClaimType.HADITH]
    assert "hadith_attribution_marker" in out.classification_signals


async def test_user_cited_hadith_requires_hadith():
    llm = FakeLLMProvider([ClassificationSuggestion(suggested_claim_type=None, rationale="r")])
    pe = ProvidedEvidence(
        provided_evidence_type=ProvidedEvidenceType.HADITH, provided_evidence_text="نص"
    )
    out = await LlmClaimClassifier(llm).classify(confirmed("الصدق فضيلة", provided_evidence=pe))
    assert out.claim_type == ClaimType.HADITH


async def test_unsupported_category_is_out_of_scope_and_llm_failure_propagates():
    llm = FakeLLMProvider([ClassificationSuggestion(suggested_claim_type=None, rationale="r")])
    out = await LlmClaimClassifier(llm).classify(confirmed("صيام الاثنين سنة"))
    assert isinstance(out, OutOfScopeOutcome)

    class Failing(FakeLLMProvider):
        async def generate_structured(self, request, output_type):
            raise LLMRateLimitedError("x")

    with pytest.raises(LLMRateLimitedError):
        await LlmClaimClassifier(Failing()).classify(confirmed("x"))


# ------------------------------------------------------------------ routing


@pytest.mark.parametrize(
    "types,expected",
    [
        ([ClaimType.QURAN], {ClaimType.QURAN: [T.QURAN]}),
        ([ClaimType.TAFSIR], {ClaimType.TAFSIR: [T.TAFSIR_AL_MUYASSAR, T.TAFSIR_IBN_KATHIR]}),
        (
            [ClaimType.ASBAB_NUZUL],
            {ClaimType.ASBAB_NUZUL: [T.ASBAB_AL_NUZUL_AL_WAHIDI, T.AL_MUHARRAR_FI_ASBAB_AL_NUZUL]},
        ),
        (
            [ClaimType.TAFSIR, ClaimType.QURAN],
            {
                ClaimType.TAFSIR: [T.TAFSIR_AL_MUYASSAR, T.TAFSIR_IBN_KATHIR],
                ClaimType.QURAN: [T.QURAN],
            },
        ),
    ],
)
async def test_router_uses_only_qualified_available_sources(types, expected):
    plan = await DeterministicSourceRouter(registry()).route(
        classified("x", types[0], extra=types[1:])
    )
    assert isinstance(plan, SourceRoutingPlan)
    assert {r.required_claim_type: r.sources for r in plan.routes} == expected


@pytest.mark.parametrize("types", [[ClaimType.HADITH], [ClaimType.QURAN, ClaimType.HADITH]])
async def test_hadith_requirement_abstains_explicitly(types):
    out = await DeterministicSourceRouter(registry(dorar_enabled=True)).route(
        classified("قال النبي ﷺ ...", types[0], extra=types[1:])
    )
    assert isinstance(out, RequiredSourceUnavailableOutcome)
    assert out.kind == "required_source_unavailable"
    assert out.unavailable_sources == [T.DORAR_HADITH]
    assert out.required_claim_types == types
    assert not hasattr(out, "status")  # never a verification status


async def test_disabled_quranpedia_makes_quran_claims_abstain():
    out = await DeterministicSourceRouter(registry(quranpedia_enabled=False)).route(
        classified("x", ClaimType.QURAN)
    )
    assert isinstance(out, RequiredSourceUnavailableOutcome) and out.unavailable_sources == [
        T.QURAN
    ]


async def test_pipeline_passes_required_source_unavailable_through_without_retrieval():
    class NoRetrieval(stubs.StubHybridRetriever):
        async def retrieve(self, claim, plan, *, attempt=0):  # pragma: no cover
            raise AssertionError("retrieval must not run")

    llm = FakeLLMProvider(
        [ClassificationSuggestion(suggested_claim_type=ClaimType.HADITH, rationale="r")]
    )
    pipeline = VerificationPipeline(
        PipelineStages(
            classifier=LlmClaimClassifier(llm),
            router=DeterministicSourceRouter(registry()),
            retriever=NoRetrieval(),
            verifier=stubs.StubEvidenceVerifier(),
            analyzer=stubs.StubEvidenceAnalyzer(),
            status=stubs.StubStatusDeterminer(),
            gate=stubs.StubFinalValidationGate(),
            builder=stubs.StubResultBuilder(),
        ),
        max_retries=2,
    )
    claim = Claim(
        original_text="x",
        confirmed_claim_text="قال رسول الله ﷺ: إنما الأعمال بالنيات",
        user_confirmation_status=UserConfirmationStatus.CONFIRMED,
    )
    [outcome] = (await pipeline.run([claim])).outcomes
    assert isinstance(outcome, RequiredSourceUnavailableOutcome)


# ------------------------------------------------------------------ retrieval


async def retrieve(claim, reg=None, attempt=0):
    reg = reg or registry()
    plan = await DeterministicSourceRouter(reg).route(claim)
    assert isinstance(plan, SourceRoutingPlan)
    return await TrustedSourceRetriever(reg).retrieve(claim, plan, attempt=attempt)


def by_source(result):
    out = {}
    for c in result.candidates:
        out.setdefault(c.retrieval.searched_source, []).append(c)
    return out


async def test_quran_quote_with_wrong_reference_retrieves_the_real_ayah():
    res = await retrieve(
        classified("قال تعالى: «إن الصفا والمروة من شعائر الله» في سورة آل عمران", ClaimType.QURAN)
    )
    [top, *_] = by_source(res)[T.QURAN]
    assert top.evidence.metadata.ayah_number == 158 and top.evidence.metadata.surah_number == 2
    assert (
        top.retrieval.match_basis == RetrievalMatchBasis.QUOTED_TEXT
        and top.retrieval.retrieval_rank == 1
    )
    assert res.insufficient_retrieval is False and res.semantic_search_attempted is False


async def test_explicit_reference_and_validated_hints():
    res = await retrieve(classified("آية الكرسي هي الآية 255 من سورة البقرة", ClaimType.QURAN))
    [c] = by_source(res)[T.QURAN]
    assert c.retrieval.match_basis == RetrievalMatchBasis.EXPLICIT_REFERENCE
    hints = [
        AyahRetrievalHint(surah_number=2, ayah_start=255),
        AyahRetrievalHint(surah_number=2, ayah_start=999),
    ]
    res = await retrieve(classified("آية الكرسي أعظم آية", ClaimType.QURAN, hints=hints))
    [c] = by_source(res)[T.QURAN]
    assert c.retrieval.match_basis == RetrievalMatchBasis.RETRIEVAL_HINT
    assert c.evidence.source_record_id == str(gid(2, 255))
    assert res.discarded_hint_count == 1  # invalid hint discarded, never used


async def test_tafsir_is_fetched_live_for_each_anchor_and_bound_book():
    seen: list[str] = []
    res = await retrieve(
        classified("معنى «لا تأخذه سنة ولا نوم» أن الله لا يأخذه نعاس", ClaimType.TAFSIR),
        registry(seen=seen),
    )
    assert sorted(seen) == ["/v1/ayah/2/255/book/136", "/v1/ayah/2/255/book/2012"]
    got = by_source(res)
    assert len(got[T.TAFSIR_IBN_KATHIR]) == 2 and len(got[T.TAFSIR_AL_MUYASSAR]) == 1
    assert T.QURAN not in got  # Source Boundary: no Quran route for a pure tafsir claim
    c = got[T.TAFSIR_IBN_KATHIR][0]
    assert c.retrieval.anchor_ayah.quranpedia_ayah_id == gid(2, 255)
    assert [r.retrieval.retrieval_rank for r in got[T.TAFSIR_IBN_KATHIR]] == [1, 2]
    assert [a.ayah_number for a in res.anchor_ayahs] == [255]


async def test_shared_multi_ayah_passage_is_deduplicated_by_fingerprint():
    def handler(r):
        s, a = r.url.path.split("/")[3:5]
        return httpx.Response(
            200,
            json={
                "book": {"id": 2919, "name": "أسباب نزول القرآن - الواحدي", "author": None},
                "content": [
                    {
                        "text": "القول في آية التسمية",
                        "part": "1",
                        "page": 2,
                        "ayahs": "1,2,3,4,5,6,7",
                    }
                ],
            }
            if r.url.path.endswith("/2919")
            else {"book": {"id": 460, "name": "المحرر"}, "content": []},
        )

    res = await retrieve(
        classified("سبب نزول الآيات 1-3 من سورة الفاتحة", ClaimType.ASBAB_NUZUL),
        registry(handler=handler),
    )
    [c] = by_source(res)[T.ASBAB_AL_NUZUL_AL_WAHIDI]
    assert [r.ayah_number for r in c.evidence.metadata.associated_ayahs] == [1, 2, 3, 4, 5, 6, 7]
    assert len([a for a in res.attempts if a.source == T.ASBAB_AL_NUZUL_AL_WAHIDI]) == 3


async def test_keyword_fallback_is_flagged_as_weak():
    res = await retrieve(classified("الحي القيوم لا يأخذه نوم ولا نعاس", ClaimType.QURAN))
    assert res.anchor_ayahs == []
    assert all(c.retrieval.match_basis == RetrievalMatchBasis.KEYWORD for c in res.candidates)
    assert res.candidates and res.insufficient_retrieval is True


async def test_nothing_found_is_a_completed_search_not_a_failure():
    res = await retrieve(classified("«وتعاونوا على الخير ففي ذلك الفلاح المبين»", ClaimType.QURAN))
    assert res.candidates == [] and res.no_candidates_after_completed_search
    assert not res.has_failed_attempts


async def test_one_failing_source_does_not_hide_the_other():
    def handler(r):
        if r.url.path.endswith("/136"):
            return httpx.Response(503)
        return httpx.Response(200, json=RESPONSES["/v1/ayah/2/255/book/2012"])

    res = await retrieve(
        classified("«لا تأخذه سنة ولا نوم» معناها", ClaimType.TAFSIR), registry(handler=handler)
    )
    failed = [a for a in res.attempts if a.status == RetrievalAttemptStatus.FAILED]
    assert [a.source for a in failed] == [T.TAFSIR_IBN_KATHIR] and failed[0].error.retryable
    assert [c.retrieval.searched_source for c in res.candidates] == [T.TAFSIR_AL_MUYASSAR]
    assert not res.all_attempts_failed


async def test_missing_quran_data_is_a_technical_failure():
    class Unsynced(QuranpediaAdapter):
        def quran_index(self):
            raise QuranDataMissingError("not synced")

    reg = AdapterRegistry()
    reg.register(Unsynced())
    reg.register(SpyDorar())
    plan = await DeterministicSourceRouter(reg).route(classified("x", ClaimType.QURAN))
    res = await TrustedSourceRetriever(reg).retrieve(classified("x", ClaimType.QURAN), plan)
    assert res.all_attempts_failed and res.candidates == []
