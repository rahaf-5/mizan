# ruff: noqa: E501  (long Arabic sample claims and report lines)
"""REAL Task 5a retrieval smoke test (Gemini classification + official Quranpedia).

    cd backend && source .venv/bin/activate
    python -m app.cli.sync_quran_dump        # once (and to update)
    python -m app.cli.smoke_retrieval

Runs fixed public claims through: classification -> deterministic routing -> retrieval.
NO verification, NO statuses, NO verdicts. Prints the traceability chain of each candidate
(Evidence -> Source -> Provider -> Original record address -> Reference/URL) and checks a
retrieval-level expectation per case. Dorar is wrapped in a spy and must never be called.
Never prints the API key.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.domain.claim import ConfirmedClaim
from app.domain.enums import RetrievalAttemptStatus, RetrievalMatchBasis, UserConfirmationStatus
from app.domain.errors import MizanError
from app.domain.results import OutOfScopeOutcome, RequiredSourceUnavailableOutcome
from app.domain.retrieval import RetrievalResult
from app.domain.trusted_sources import TrustedSourceId as T
from app.llm.factory import build_llm_provider
from app.pipeline.classification import LlmClaimClassifier
from app.pipeline.retrieval import TrustedSourceRetriever
from app.pipeline.routing import DeterministicSourceRouter
from app.sources.dorar import DorarAdapter
from app.sources.quran_index import QuranDataMissingError, QuranIndex
from app.sources.quranpedia import QuranpediaAdapter
from app.sources.registry import AdapterRegistry


class SpyDorar(DorarAdapter):
    calls = 0

    async def search(self, query):  # type: ignore[no-untyped-def]
        SpyDorar.calls += 1
        return await super().search(query)

    async def get_records(self, source, source_address):  # type: ignore[no-untyped-def]
        SpyDorar.calls += 1
        return await super().get_records(source, source_address)


@dataclass
class Case:
    name: str
    text: str
    expect: str
    check: Callable[[object], str | None]  # returns None if OK, else a failure reason


def _cands(res, source):  # type: ignore[no-untyped-def]
    return [c for c in res.candidates if c.retrieval.searched_source == source]


def _has_ayah(res, source, s, a, basis=None):  # type: ignore[no-untyped-def]
    for c in _cands(res, source):
        md = c.evidence.metadata
        loc = (
            (md.surah_number, md.ayah_number)
            if source == T.QURAN
            else (c.retrieval.anchor_ayah.surah_number, c.retrieval.anchor_ayah.ayah_number)
        )
        if loc == (s, a) and (basis is None or c.retrieval.match_basis == basis):
            return True
    return False


def need(cond: bool, reason: str) -> str | None:
    return None if cond else reason


def is_result(out: object) -> bool:
    return isinstance(out, RetrievalResult)


CASES = [
    Case(
        "quran_quote",
        "«اللَّهُ لَا إِلَٰهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ» هي بداية آية الكرسي في سورة البقرة",
        "Quran candidate 2:255 matched by quoted text",
        lambda r: need(
            is_result(r) and _has_ayah(r, T.QURAN, 2, 255, RetrievalMatchBasis.QUOTED_TEXT),
            "no quoted-text Quran match at 2:255",
        ),
    ),
    Case(
        "quran_wrong_reference",
        "قال تعالى في سورة آل عمران: «إن الصفا والمروة من شعائر الله»",
        "Quran candidate 2:158 (the real location) retrieved; no verdict",
        lambda r: need(is_result(r) and _has_ayah(r, T.QURAN, 2, 158), "2:158 not retrieved"),
    ),
    Case(
        "quran_explicit_reference",
        "آية الكرسي هي الآية 255 من سورة البقرة",
        "Quran candidate 2:255",
        lambda r: need(is_result(r) and _has_ayah(r, T.QURAN, 2, 255), "2:255 not retrieved"),
    ),
    Case(
        "quran_fabricated_quote",
        "قال تعالى: «وتعاونوا على الخير ففي ذلك الفلاح المبين»",
        "no quoted-text match (exact search completed; weak/none is not 'false')",
        lambda r: need(
            is_result(r)
            and not any(
                c.retrieval.match_basis == RetrievalMatchBasis.QUOTED_TEXT for c in r.candidates
            )
            and any(a.status == RetrievalAttemptStatus.COMPLETED for a in r.attempts),
            "unexpected quoted-text match or no completed search",
        ),
    ),
    Case(
        "tafsir_ayat_alkursi",
        "معنى قوله تعالى «لا تأخذه سنة ولا نوم» في آية الكرسي: أن الله لا يغلبه نعاس ولا نوم",
        "Muyassar (2012) and Ibn Kathir (136) passages anchored at 2:255",
        lambda r: need(
            is_result(r)
            and _has_ayah(r, T.TAFSIR_AL_MUYASSAR, 2, 255)
            and _has_ayah(r, T.TAFSIR_IBN_KATHIR, 2, 255),
            "missing Muyassar or Ibn Kathir passage at 2:255",
        ),
    ),
    Case(
        "asbab_safa_marwa",
        "نزل قوله تعالى «إن الصفا والمروة من شعائر الله» في الأنصار الذين كانوا يتحرجون من الطواف بينهما",
        "al-Wahidi (2919) and al-Muharrar (460) passages at 2:158; relation_type unspecified",
        lambda r: need(
            is_result(r)
            and _has_ayah(r, T.ASBAB_AL_NUZUL_AL_WAHIDI, 2, 158)
            and _has_ayah(r, T.AL_MUHARRAR_FI_ASBAB_AL_NUZUL, 2, 158)
            and all(
                c.evidence.metadata.relation_type.value == "unspecified"
                for c in r.candidates
                if c.evidence.source_type.value == "asbab_nuzul"
            ),
            "missing Wahidi/Muharrar passage at 2:158 or relation_type not unspecified",
        ),
    ),
    Case(
        "asbab_multi_ayah_association",
        "نزلت سورة الفاتحة بمكة، وهذا مذكور في سبب نزول الآية 1 من سورة الفاتحة",
        "a Wahidi passage whose provider association covers several ayahs (kept, not collapsed)",
        lambda r: need(
            is_result(r)
            and any(
                len(c.evidence.metadata.associated_ayahs) > 1
                for c in _cands(r, T.ASBAB_AL_NUZUL_AL_WAHIDI)
            ),
            "no multi-ayah Wahidi association found",
        ),
    ),
    Case(
        "hadith_required",
        "قال رسول الله ﷺ: «إنما الأعمال بالنيات»",
        "required_source_unavailable (Dorar) — explicit abstention, no Dorar call",
        lambda r: need(
            isinstance(r, RequiredSourceUnavailableOutcome)
            and r.unavailable_sources == [T.DORAR_HADITH],
            "did not abstain as required_source_unavailable",
        ),
    ),
    Case(
        "composite_quran_hadith",
        "«إن الله مع الصابرين» آية في سورة البقرة، وقال النبي ﷺ: «الصبر ضياء»",
        "whole claim required_source_unavailable",
        lambda r: need(
            isinstance(r, RequiredSourceUnavailableOutcome), "composite claim did not abstain"
        ),
    ),
]


def show_result(res: RetrievalResult, out: Callable[[str], None]) -> None:
    out(
        f"  anchors: {[f'{a.surah_number}:{a.ayah_number}' for a in res.anchor_ayahs]} "
        f"discarded_hints={res.discarded_hint_count} weak={res.insufficient_retrieval} "
        f"semantic_attempted={res.semantic_search_attempted}"
    )
    for a in res.attempts:
        if a.status == RetrievalAttemptStatus.FAILED:
            out(
                f"  FAILED attempt {a.source.value} {a.method.value}: {a.error.code.value} {a.error.message}"
            )
    for c in res.candidates:
        ev, rt, md = c.evidence, c.retrieval, c.evidence.metadata
        assoc = getattr(md, "provider_ayah_association", None)
        author = getattr(md, "provider_author", "—")
        out(
            f"  #{rt.retrieval_rank} [{rt.searched_source.value}] {rt.retrieval_method.value}/"
            f"{rt.match_basis.value if rt.match_basis else '-'} score={rt.similarity_score}"
        )
        out(
            f"     evidence→source: {ev.source_name} | provider: {ev.provider.value} | "
            f"record: {ev.source_address} (record_id={ev.source_record_id}) | channel={ev.retrieval_channel.value} "
            f"version={ev.source_version}"
        )
        out(f"     reference: {ev.reference} | url: {ev.source_url}")
        out(
            f"     sha256={ev.text_sha256[:16]}… retrieved_at={ev.retrieved_at.isoformat()} "
            f"provider_author={author!r} association={assoc!r}"
        )
        out(f"     text: {ev.text[:90].replace(chr(10), ' ')}…")


async def run(out: Callable[[str], None] = print) -> int:
    settings = get_settings()
    llm = build_llm_provider(settings)
    if llm is None or not llm.is_configured():
        out("LLM not configured (set LLM_PROVIDER=gemini and GEMINI_API_KEY in backend/.env).")
        return 2
    try:
        index = QuranIndex.load(Path(settings.quran_data_dir) if settings.quran_data_dir else None)
    except QuranDataMissingError as exc:
        out(f"{exc}")
        return 2
    out(f"Quran: Quranpedia Mushaf {index.mushaf_id}, version {index.version}")
    reg = AdapterRegistry()
    reg.register(
        QuranpediaAdapter(
            enabled=True, quran_index=index, timeout_seconds=settings.source_request_timeout_seconds
        )
    )
    reg.register(SpyDorar(enabled=True))  # config cannot override the policy block
    classifier = LlmClaimClassifier(llm)
    router = DeterministicSourceRouter(reg)
    retriever = TrustedSourceRetriever(reg)

    failures = 0
    for i, case in enumerate(CASES, 1):
        out(
            f"\n=== [{i}/{len(CASES)}] {case.name} ===\n  claim: {case.text}\n  expect: {case.expect}"
        )
        claim = ConfirmedClaim(
            claim_id=case.name,
            confirmed_claim_text=case.text,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED,
        )
        result: object
        try:
            classified = await classifier.classify(claim)
            if isinstance(classified, OutOfScopeOutcome):
                result = classified
                out(f"  classification: OUT OF SCOPE ({classified.reason.value})")
            else:
                out(
                    f"  classification: {[t.value for t in classified.required_claim_types]} "
                    f"hints={[(h.surah_number, h.ayah_start, h.ayah_end) for h in classified.retrieval_hints]} "
                    f"signals={classified.classification_signals}"
                )
                plan = await router.route(classified)
                if isinstance(plan, RequiredSourceUnavailableOutcome):
                    result = plan
                    out(
                        f"  routing: REQUIRED SOURCE UNAVAILABLE {[s.value for s in plan.unavailable_sources]}"
                    )
                else:
                    out(
                        f"  routing: {[(r.required_claim_type.value, [s.value for s in r.sources]) for r in plan.routes]}"
                    )
                    result = await retriever.retrieve(classified, plan)
                    show_result(result, out)
        except MizanError as exc:
            info = exc.to_info()
            out(f"  SYSTEM ERROR {info.code.value}: {info.message}")
            result = None
        reason = case.check(result)
        if reason:
            failures += 1
        out(f"  -> {'PASS' if reason is None else 'FAIL: ' + reason}")
        await asyncio.sleep(1.5)  # gentle on the Gemini free tier and Quranpedia limits

    out(f"\nDorar calls: {SpyDorar.calls} (must be 0)")
    if SpyDorar.calls:
        failures += 1
    out(
        f"RESULT: {len(CASES) - failures}/{len(CASES)} cases passed"
        if not SpyDorar.calls
        else "RESULT: FAIL (Dorar was called)"
    )
    return 0 if failures == 0 else 1


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
