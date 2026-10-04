"""Quranpedia adapter: official addresses, faithful metadata, traceability, failures.

Response shapes mirror what the official API returned live (docs/SOURCE_VALIDATION.md);
texts are shortened. All HTTP is mocked.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from app.domain.enums import (
    AsbabRelationType,
    RetrievalChannel,
    RetrievalMatchBasis,
    RetrievalMethod,
)
from app.domain.errors import SourceUnavailableError
from app.domain.evidence import text_fingerprint
from app.domain.trusted_sources import TrustedSourceId as T
from app.sources.base import SourceQuery
from app.sources.quranpedia import QuranpediaAdapter, html_to_text
from tests.quran_fixture import gid, make_index

INDEX = make_index()
NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
AUTHOR_IK = {"id": 7634, "ar_name": "ابن كثير", "full_name": "x"}


def book(book_id, name, author=None):
    return {"id": book_id, "name": name, "short_name": "", "author": author}


RESPONSES = {
    "/v1/ayah/2/255/book/136": {
        "book": book(136, "تفسير القرآن العظيم", AUTHOR_IK),
        "content": [
            {
                "text": '<p>قوله: <span class="book-ayah">لا تأخذه سنة</span></p>نعاس<br />\r\nنوم',
                "part": "1",
                "page": 672,
                "ayahs": str(gid(2, 255)),
            },
            {"text": "طريق آخر", "part": "1", "page": 673, "ayahs": str(gid(2, 255))},
            {"text": "عنصر غير قابل للتتبع", "part": "1", "page": 673, "ayahs": "999999"},
        ],
    },
    "/v1/ayah/2/255/book/2012": {
        "book": book(
            2012, "التفسير الميسر", {"id": 14362, "ar_name": "مجمع الملك فهد لطباعة المصحف الشريف"}
        ),
        "content": [
            {
                "text": "الله الذي لا يستحق الألوهية إلا هو",
                "part": "1",
                "page": str(gid(2, 255)),
                "ayahs": str(gid(2, 255)),
            }
        ],
    },
    "/v1/ayah/1/1/book/2919": {
        "book": book(2919, "أسباب نزول القرآن - الواحدي", None),
        "content": [
            {
                "text": "القول في آية التسمية<br />\r\nأخبرنا",
                "part": "1",
                "page": 2,
                "ayahs": "1,2,3,4,5,6,7",
            }
        ],
    },
}


def make(handler=None, seen=None, **kw):
    def default(r: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(r)
        body = RESPONSES.get(r.url.path)
        return (
            httpx.Response(200, json=body)
            if body
            else httpx.Response(200, json={"book": {"id": 0}, "content": []})
        )

    return QuranpediaAdapter(
        quran_index=INDEX,
        transport=httpx.MockTransport(handler or default),
        clock=lambda: NOW,
        **kw,
    )


def anchor(s, a):
    return INDEX.get(s, a).ref


def test_html_to_text_is_deterministic_plain_text():
    assert html_to_text("<p>أ<span class='x'>ب</span></p>ج<br />\r\nد &amp; ﻿") == "أب\nج\nد &"


async def test_tafsir_passages_are_traceable_without_invented_ids():
    seen: list = []
    hits = await make(seen=seen).search(
        SourceQuery(
            source=T.TAFSIR_IBN_KATHIR,
            method=RetrievalMethod.EXACT,
            query_text="لا تأخذه سنة ولا نوم",
            anchor=anchor(2, 255),
            basis=RetrievalMatchBasis.QUOTED_TEXT,
        )
    )
    assert [str(r.url) for r in seen] == ["https://api.quranpedia.net/v1/ayah/2/255/book/136"]
    assert len(hits) == 2  # the untraceable item (unknown ayah id) is dropped, not guessed
    ev = hits[0].evidence
    assert ev.source_address == "/v1/ayah/2/255/book/136"
    assert str(ev.source_url) == "https://api.quranpedia.net/v1/ayah/2/255/book/136"
    assert ev.source_record_id is None and ev.retrieval_channel == RetrievalChannel.LIVE_API
    assert ev.retrieved_at == NOW and ev.text_sha256 == text_fingerprint(ev.text)
    assert ev.text == "قوله: لا تأخذه سنة\nنعاس\nنوم"
    md = ev.metadata
    assert (md.provider_book_id, md.provider_author, md.page_kind) == (136, "ابن كثير", "printed")
    assert (md.provider_part, md.provider_page, md.position_in_response) == ("1", "672", 0)
    assert "الجزء 1، الصفحة 672" in ev.reference and "سورة البقرة، الآية 255" in ev.reference
    assert ev.source_name == "تفسير ابن كثير"  # approved-source identity (policy)
    assert hits[0].score is not None and hits[0].anchor_ayah == anchor(2, 255)


async def test_muyassar_2012_page_is_not_presented_as_a_printed_page():
    [hit] = await make().search(
        SourceQuery(
            source=T.TAFSIR_AL_MUYASSAR, method=RetrievalMethod.EXACT, anchor=anchor(2, 255)
        )
    )
    md = hit.evidence.metadata
    assert md.page_kind == "none" and md.provider_page == "262"  # kept verbatim, not relabelled
    assert "الصفحة" not in hit.evidence.reference


async def test_wahidi_multi_ayah_association_and_null_author_preserved():
    [hit] = await make().search(
        SourceQuery(
            source=T.ASBAB_AL_NUZUL_AL_WAHIDI, method=RetrievalMethod.EXACT, anchor=anchor(1, 1)
        )
    )
    ev = hit.evidence
    md = ev.metadata
    assert md.provider_ayah_association == "1,2,3,4,5,6,7"
    assert [r.ayah_number for r in md.associated_ayahs] == [1, 2, 3, 4, 5, 6, 7]
    assert md.ayah_range == (1, 1, 7)
    assert md.provider_author is None  # never filled in
    assert md.relation_type == AsbabRelationType.UNSPECIFIED
    assert ev.source_name == "أسباب النزول للواحدي" and md.page_kind == "provider"


async def test_no_response_caching_each_search_is_a_live_request():
    seen: list = []
    a = make(seen=seen)
    q = SourceQuery(
        source=T.TAFSIR_AL_MUYASSAR, method=RetrievalMethod.EXACT, anchor=anchor(2, 255)
    )
    await a.search(q)
    await a.search(q)
    assert len(seen) == 2


@pytest.mark.parametrize("status,retryable", [(429, True), (500, True), (503, True), (404, False)])
async def test_http_failures_are_system_errors(status, retryable):
    a = make(handler=lambda r: httpx.Response(status, json={"error": "x"}))
    with pytest.raises(SourceUnavailableError) as e:
        await a.search(
            SourceQuery(
                source=T.TAFSIR_IBN_KATHIR, method=RetrievalMethod.EXACT, anchor=anchor(2, 255)
            )
        )
    assert e.value.retryable is retryable


async def test_network_error_and_wrong_book_are_system_errors():
    def boom(r):
        raise httpx.ConnectError("down")

    with pytest.raises(SourceUnavailableError):
        await make(handler=boom).search(
            SourceQuery(
                source=T.TAFSIR_IBN_KATHIR, method=RetrievalMethod.EXACT, anchor=anchor(2, 255)
            )
        )
    wrong = make(handler=lambda r: httpx.Response(200, json={"book": book(32, "x"), "content": []}))
    with pytest.raises(SourceUnavailableError):
        await wrong.search(
            SourceQuery(
                source=T.TAFSIR_AL_MUYASSAR, method=RetrievalMethod.EXACT, anchor=anchor(2, 255)
            )
        )


async def test_invalid_anchor_is_rejected():
    from app.domain.evidence import AyahRef

    bad = AyahRef(surah_number=2, ayah_number=255, quranpedia_ayah_id=1)
    with pytest.raises(ValueError):
        await make().search(
            SourceQuery(source=T.TAFSIR_IBN_KATHIR, method=RetrievalMethod.EXACT, anchor=bad)
        )


async def test_quran_evidence_from_official_dump():
    a = make()
    [hit] = await a.search(
        SourceQuery(
            source=T.QURAN,
            method=RetrievalMethod.EXACT,
            ayah_refs=[anchor(2, 255)],
            basis=RetrievalMatchBasis.EXPLICIT_REFERENCE,
        )
    )
    ev = hit.evidence
    assert ev.source_address == "/v1/mushafs/1/2/255" and ev.source_record_id == "262"
    assert (
        ev.retrieval_channel == RetrievalChannel.OFFICIAL_DUMP and ev.source_version == "2026-10-02"
    )
    assert ev.reference == "سورة البقرة، الآية 255"
    assert ev.metadata.text_form.value == "mushaf_diacritized"
    assert not hasattr(ev.metadata, "ayah_text_uthmani")
    quotes = await a.search(
        SourceQuery(
            source=T.QURAN,
            method=RetrievalMethod.EXACT,
            query_text="إن الصفا والمروة من شعائر الله",
        )
    )
    assert [h.evidence.metadata.ayah_number for h in quotes] == [158]
    assert quotes[0].match_basis == RetrievalMatchBasis.QUOTED_TEXT


async def test_get_records_by_official_address():
    a = make()
    [q] = await a.get_records(T.QURAN, "/v1/mushafs/1/2/255")
    assert q.source_record_id == "262"
    passages = await a.get_records(T.TAFSIR_IBN_KATHIR, "/v1/ayah/2/255/book/136")
    assert len(passages) == 2
    with pytest.raises(ValueError):
        await a.get_records(T.TAFSIR_IBN_KATHIR, "/v1/ayah/2/255/book/331")  # not the bound edition
