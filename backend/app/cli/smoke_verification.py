# ruff: noqa: E501  (long Arabic sample claims and report lines)
"""REAL Task 5b verification smoke test (Gemini + official Quranpedia; Dorar must stay unused).

    cd backend && source .venv/bin/activate
    python -m app.cli.sync_quran_dump
    python -m app.cli.smoke_verification

Runs fixed public claims through the full pipeline (classification -> routing -> retrieval ->
verification -> analysis -> status -> Final Validation Gate) and checks each outcome against an
expected set. Prints components (what was right / wrong), assessments with verbatim spans and
the traceability chain of every evidence item. Never prints the API key.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.cli.smoke_retrieval import SpyDorar
from app.config import get_settings
from app.domain.claim import ConfirmedClaim
from app.domain.enums import UserConfirmationStatus
from app.domain.evidence import text_fingerprint
from app.domain.results import (
    OutOfScopeOutcome,
    RequiredSourceUnavailableOutcome,
    SystemErrorOutcome,
    VerificationOutcome,
)
from app.llm.factory import build_llm_provider
from app.pipeline.factory import build_verification_pipeline
from app.sources.quran_index import QuranDataMissingError, QuranIndex
from app.sources.quranpedia import QuranpediaAdapter
from app.sources.registry import AdapterRegistry


@dataclass
class Case:
    name: str
    text: str
    expected: set[str]  # status values or outcome kinds
    note: str = ""


CASES = [
    Case(
        "quran_quote_correct_surah",
        "قال تعالى في سورة البقرة: «إن الصفا والمروة من شعائر الله»",
        {"supported"},
    ),
    Case(
        "quran_quote_wrong_surah",
        "قال تعالى في سورة آل عمران: «إن الصفا والمروة من شعائر الله»",
        {"contradicted"},
        "quote supported, location contradicted, real location shown",
    ),
    Case(
        "quran_fabricated_quote",
        "قال تعالى: «وتعاونوا على الخير ففي ذلك الفلاح المبين»",
        {"no_evidence_found"},
    ),
    Case("quran_quote_exists", "«إن الله مع الصابرين» آية من القرآن الكريم", {"supported"}),
    Case(
        "tafsir_muyassar_supported",
        "معنى قوله تعالى «لا تأخذه سنة ولا نوم» أن الله لا يأخذه نعاس ولا نوم",
        {"supported", "partially_supported"},
        "Gemini-dependent",
    ),
    Case(
        "tafsir_wrong_meaning",
        "معنى قوله تعالى «لا تأخذه سنة ولا نوم» أن الله لا يغضب على عباده",
        {"contradicted", "insufficient_evidence", "no_evidence_found"},
        "must NOT be supported",
    ),
    Case(
        "asbab_ansar_supported",
        "نزل قوله تعالى «إن الصفا والمروة من شعائر الله» في الأنصار الذين كانوا يتحرجون من الطواف بينهما",
        {"supported", "partially_supported"},
        "Gemini-dependent; relation_type stays unspecified",
    ),
    Case(
        "asbab_wrong_event",
        "نزل قوله تعالى «إن الصفا والمروة من شعائر الله» في غزوة بدر",
        {"contradicted", "insufficient_evidence", "no_evidence_found"},
        "must NOT be supported",
    ),
    Case(
        "asbab_partial",
        "نزل قوله تعالى «إن الصفا والمروة من شعائر الله» في الأنصار، وكان ذلك في السنة الأولى من الهجرة",
        {"partially_supported", "contradicted", "insufficient_evidence"},
        "must NOT be supported",
    ),
    Case(
        "ayah_name_insufficient",
        "آية الكرسي هي الآية 255 من سورة البقرة",
        {"insufficient_evidence"},
    ),
    Case(
        "hadith_unavailable",
        "قال رسول الله ﷺ: «إنما الأعمال بالنيات»",
        {"required_source_unavailable"},
    ),
    Case(
        "composite_quran_hadith",
        "«إن الله مع الصابرين» آية في سورة البقرة، وقال النبي ﷺ: «الصبر ضياء»",
        {"required_source_unavailable"},
    ),
    Case("out_of_scope_fiqh", "صيام يوم الاثنين واجب على كل مسلم", {"out_of_scope"}),
]


def label(o) -> str:  # type: ignore[no-untyped-def]
    return o.status.value if isinstance(o, VerificationOutcome) else o.kind


def show(o, out: Callable[[str], None]) -> list[str]:  # type: ignore[no-untyped-def]
    problems: list[str] = []
    if isinstance(o, VerificationOutcome):
        failed = [c.check.value for c in o.validation.checks if not c.passed]
        out(
            f"  status: {o.status.value} | gate: {o.validation.outcome.value} failed_checks={failed}"
        )
        for c in o.analysis.components:
            loc = ", ".join(f"{r.surah_number}:{r.ayah_number}" for r in c.verified_location)
            out(
                f"   • [{c.kind.value}/{c.claim_type.value}] «{c.text[:60]}» -> {c.outcome.value if c.outcome else '-'}"
                + (f" | verified: {loc}" if loc else "")
                + (f" | {c.detail}" if c.detail else "")
            )
        by_id = {e.evidence_id: e for e in o.evidence}
        for a in o.analysis.assessments:
            ev = by_id.get(a.evidence_id)
            out(
                f"     - {a.relationship.value} ({a.assessed_by}) {ev.source_name if ev else '?'} span=«{(a.evidence_span or '')[:70]}»"
            )
        for e in o.evidence:
            ok = e.text_sha256 == text_fingerprint(e.text) and bool(e.source_address)
            if not ok:
                problems.append(f"traceability broken for {e.evidence_id}")
            md = e.metadata
            out(
                f"     ⛓ {e.source_name} → {e.provider.value} → {e.source_address} → {e.reference} "
                f"| sha256={e.text_sha256[:12]}… relation_type={getattr(md, 'relation_type', None)}"
            )
            if (
                getattr(md, "relation_type", None) is not None
                and md.relation_type.value != "unspecified"
            ):
                problems.append("asbab relation_type must stay unspecified")
        if o.analysis.related_unverified_addresses:
            out(
                f"   related/unverified (keyword-only, not counted): {o.analysis.related_unverified_addresses[:5]}"
            )
    elif isinstance(o, RequiredSourceUnavailableOutcome):
        out(
            f"  REQUIRED SOURCE UNAVAILABLE: {[s.value for s in o.unavailable_sources]} (types {[t.value for t in o.required_claim_types]})"
        )
    elif isinstance(o, OutOfScopeOutcome):
        out(f"  OUT OF SCOPE: {o.reason.value}")
    elif isinstance(o, SystemErrorOutcome):
        out(
            f"  SYSTEM ERROR {o.error.code.value} @ {o.error.stage.value if o.error.stage else '-'}: {o.error.message}"
        )
    return problems


async def run(out: Callable[[str], None] = print) -> int:
    settings = get_settings()
    llm = build_llm_provider(settings)
    if llm is None or not llm.is_configured():
        out("LLM not configured (set LLM_PROVIDER=gemini and GEMINI_API_KEY in backend/.env).")
        return 2
    try:
        index = QuranIndex.load(Path(settings.quran_data_dir) if settings.quran_data_dir else None)
    except QuranDataMissingError as exc:
        out(str(exc))
        return 2
    out(f"Quran: Quranpedia Mushaf {index.mushaf_id}, version {index.version}")
    reg = AdapterRegistry()
    reg.register(
        QuranpediaAdapter(
            enabled=True, quran_index=index, timeout_seconds=settings.source_request_timeout_seconds
        )
    )
    reg.register(SpyDorar(enabled=True))  # config cannot override the policy block
    pipeline = build_verification_pipeline(settings, llm, reg)

    passed = 0
    for i, case in enumerate(CASES, 1):
        out(
            f"\n=== [{i}/{len(CASES)}] {case.name} ===\n  claim: {case.text}\n  expected: {sorted(case.expected)} {case.note}"
        )
        claim = ConfirmedClaim(
            claim_id=case.name,
            confirmed_claim_text=case.text,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED,
        )
        [outcome] = (await pipeline.run_confirmed([claim])).outcomes
        problems = show(outcome, out)
        got = label(outcome)
        if got not in case.expected:
            problems.append(f"got {got}")
        out("  -> PASS" if not problems else f"  -> FAIL: {'; '.join(problems)}")
        passed += not problems
        await asyncio.sleep(5)  # gentle on the Gemini free-tier rate limit and Quranpedia

    out(f"\nDorar calls: {SpyDorar.calls} (must be 0)")
    ok = passed == len(CASES) and SpyDorar.calls == 0
    out(
        f"RESULT: {passed}/{len(CASES)} cases passed"
        + ("" if SpyDorar.calls == 0 else " — FAIL: Dorar was called")
    )
    return 0 if ok else 1


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
