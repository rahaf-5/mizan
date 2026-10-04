"""Source-integration validation CLI (pre-Task 5). Mocked HTTP only.

Fixtures mirror the response STRUCTURE observed live from the official APIs on
2026-10-04 (values shortened). They are not used as evidence anywhere.
"""

from __future__ import annotations

import json

import httpx

from app.cli.validate_sources import (
    DORAR_LABELS,
    QURANPEDIA_REQUESTS,
    analyse_dorar,
    analyse_quranpedia,
    parse_dorar_result,
    run_validation,
    text_checks,
)

# Structure as returned by dorar_api.json (note the unbalanced </span> after the narrator).
DORAR_HTML = (
    '<head>\n    <link rel="canonical" href="https://dorar.net/dorar_api.json">\n</head>\n'
    '<div class="hadith" style="text-align:justify;">1 -  <span class="search-keys">إنَّما</span>'
    ' <span class="search-keys">الأعمالُ</span>'
    ' <span class="search-keys">بالنِّيَّاتِ</span>  .</div>\n\n'
    '<div class="hadith-info">\n'
    '    <span class="info-subtitle">الراوي:</span> عمر بن الخطاب</span>\n'
    '    <span class="info-subtitle">المحدث:</span> ابن تيمية\n'
    '    <span class="info-subtitle">المصدر:</span>  مجموع الفتاوى\n'
    '    <span class="info-subtitle">الصفحة أو الرقم:</span>  18/24\n'
    '    <span class="info-subtitle">خلاصة حكم المحدث:</span>  <span >صحيح غريب</span>\n'
    "</div>\n--------------\n<br/><br/><br/>\n"
    '<a href="https://dorar.net/hadith/search?q=إنما الأعمال بالنيات">المزيد</a>'
)

TAFSIR = {
    "book": {"id": 2012, "name": "التفسير الميسر", "author": {"id": 14362, "ar_name": "x"}},
    "content": [{"text": "نص<br />", "part": "1", "page": "262", "ayahs": "262"}],
}


def test_dorar_parser_reads_all_labels_despite_malformed_html():
    p = parse_dorar_result(DORAR_HTML)
    assert len(p.blocks) == 1
    b = p.blocks[0]
    assert set(DORAR_LABELS) <= set(b.fields)
    assert b.fields["المحدث"] == "ابن تيمية"
    assert b.fields["الصفحة أو الرقم"] == "18/24"
    assert b.fields["خلاصة حكم المحدث"] == "صحيح غريب"
    assert "إنَّما" in b.hadith_text
    # Only the canonical link + the "more" search link — no per-hadith record URL.
    assert p.hrefs == ["https://dorar.net/hadith/search?q=إنما الأعمال بالنيات"]


def test_dorar_analysis_reports_missing_record_identifiers():
    notes = "\n".join(
        analyse_dorar("application/json", json.dumps({"ahadith": {"result": DORAR_HTML}}))
    )
    assert "per-hadith id/data-* attribute present: False" in notes
    assert "blocks with all 5 labels: 1/1" in notes


def test_dorar_non_json_is_flagged_not_parsed():
    notes = analyse_dorar("text/javascript", 'cb({"ahadith":{}})')
    assert any("NOT plain JSON" in n for n in notes)


def test_quranpedia_analysis_flags_missing_chunk_id_and_html():
    notes = "\n".join(analyse_quranpedia("/ayah/2/255/book/2012", TAFSIR))
    assert "content item id-like keys: NONE" in notes
    assert "'contains_html_tags': True" in notes


def test_text_checks_detect_bom_and_rasm_markers():
    t = text_checks("﻿اللَّهُ لَا إِلَٰهَ ۚ")
    assert t["starts_with_BOM_U+FEFF"] and t["has_dagger_alef_U+0670"]
    assert t["has_quranic_waqf_marks_U+06D6-06DC"]
    assert not t["has_alef_wasla_U+0671 (Uthmani rasm marker)"]


async def test_runner_only_calls_official_hosts_with_fixed_public_requests():
    seen: list[httpx.Request] = []

    def handler(r: httpx.Request) -> httpx.Response:
        seen.append(r)
        if r.url.host == "dorar.net":
            return httpx.Response(200, json={"ahadith": {"result": DORAR_HTML}})
        return httpx.Response(200, json=TAFSIR)

    lines: list[str] = []
    code = await run_validation(transport=httpx.MockTransport(handler), delay=0, out=lines.append)
    assert code == 0
    assert {r.url.host for r in seen} == {"api.quranpedia.net", "dorar.net"}
    assert len(seen) == len(QURANPEDIA_REQUESTS) + 1
    assert all(r.method == "GET" for r in seen)
    assert all("authorization" not in r.headers and "x-goog-api-key" not in r.headers for r in seen)
    assert all(not r.content for r in seen)  # nothing sent but the fixed URL


async def test_runner_reports_failures_without_crashing():
    def handler(r: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "Too many requests."})

    lines: list[str] = []
    code = await run_validation(transport=httpx.MockTransport(handler), delay=0, out=lines.append)
    assert code == 1
    assert any("HTTP 429" in line for line in lines)


async def test_dump_inspection_checks_sha_and_reports_missing_passage_ids():
    import gzip
    import hashlib

    from app.cli.validate_sources import DUMP_FILES, run_dump_inspection

    body = gzip.compress(json.dumps(TAFSIR, ensure_ascii=False).encode())
    manifest = {
        "version": "v",
        "license": {"attribution": "x"},
        "files": [{"name": n, "sha256": hashlib.sha256(body).hexdigest()} for n in DUMP_FILES],
    }
    hosts: set[str] = set()

    def handler(r: httpx.Request) -> httpx.Response:
        hosts.add(r.url.host)
        if r.url.path.endswith("manifest.json"):
            return httpx.Response(200, json=manifest)
        if r.url.path.endswith("/changes"):
            return httpx.Response(200, json={"changes": {"ayah_book_contents": {"rows": []}}})
        return httpx.Response(200, content=body)

    lines: list[str] = []
    code = await run_dump_inspection(transport=httpx.MockTransport(handler), out=lines.append)
    text = "\n".join(lines)
    assert code == 0
    assert hosts == {"quranpedia.net", "api.quranpedia.net"}
    assert "sha256 matches manifest: True" in text
    assert "content item id-like keys: NONE" in text
