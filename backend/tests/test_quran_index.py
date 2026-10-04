"""Mushaf 1 index: resolution of quotes / references / hints / keywords (no verdicts)."""

from __future__ import annotations

import gzip
import hashlib
import json

import pytest

from app.domain.claim import AyahRetrievalHint
from app.sources.quran_index import (
    DUMP_FILE,
    META_FILE,
    QuranDataMissingError,
    QuranIndex,
)
from tests.quran_fixture import gid, make_index, mushaf_payload


@pytest.fixture(scope="module")
def index():
    return make_index()


def test_text_is_provider_text_without_bom_and_ids_are_provider_ids(index):
    a = index.get(2, 255)
    assert not a.text.startswith("﻿") and a.text.startswith("اللَّهُ")
    assert a.quranpedia_ayah_id == gid(2, 255) == 262
    assert a.surah_name_ar == "سورة البقرة"


def test_expected_total_is_enforced():
    with pytest.raises(ValueError):
        QuranIndex.from_payload(mushaf_payload(), version="v")  # not 6,236 ayahs


def test_quote_without_diacritics_resolves_to_the_ayah(index):
    [m, *_] = index.find_quotes("قال تعالى: «إن الصفا والمروة من شعائر الله» في سورة آل عمران")
    assert [(a.surah_number, a.ayah_number) for a in m.ayahs] == [(2, 158)]
    assert m.matched_words >= 4


def test_quote_spanning_consecutive_ayahs(index):
    [m, *_] = index.find_quotes("الرحمن الرحيم مالك يوم الدين اياك نعبد")
    assert [(a.surah_number, a.ayah_number) for a in m.ayahs] == [(1, 3), (1, 4), (1, 5)]


def test_short_fragment_is_not_a_quote(index):
    assert index.find_quotes("لا تأخذه سنة") == []


@pytest.mark.parametrize(
    "text,expected",
    [
        ("آية الكرسي هي الآية 255 من سورة البقرة", [(2, 255)]),
        ("سورة البقرة الآية ٢٥٥", [(2, 255)]),
        ("[البقرة: 158]", [(2, 158)]),
        ("الآيات 1-3 من سورة الفاتحة", [(1, 1), (1, 2), (1, 3)]),
        ("سورة آل عمران آية 2", [(3, 2)]),
        ("سورة البقرة الآية 999", []),  # does not exist -> never guessed
        ("سورة البقرة", []),  # surah only -> no ayah anchor
        ("في البقرة 255 بقرة", []),  # no explicit reference form
    ],
)
def test_explicit_references(index, text, expected):
    got = index.parse_references(text)
    assert [(a.surah_number, a.ayah_number) for a in got] == expected


def test_hint_validation(index):
    assert [
        a.ayah_number
        for a in index.validate_hint(AyahRetrievalHint(surah_number=2, ayah_start=255))
    ] == [255]
    assert index.validate_hint(AyahRetrievalHint(surah_number=2, ayah_start=300)) is None
    assert index.validate_hint(AyahRetrievalHint(surah_number=200, ayah_start=1)) is None
    assert index.validate_hint(AyahRetrievalHint(surah_number=2, ayah_start=5, ayah_end=4)) is None
    assert index.validate_hint(AyahRetrievalHint(surah_number=2, ayah_start=1, ayah_end=40)) is None


def test_keyword_search_is_weak_overlap_only(index):
    [(top, score), *_] = index.keyword_search("الحي القيوم لا يأخذه نوم")
    assert (top.surah_number, top.ayah_number) == (2, 255) and score > 0
    assert index.keyword_search("كلمة") == []  # needs >= 2 distinct keywords


def _write(tmp_path, payload, sha=None):
    raw = gzip.compress(json.dumps(payload).encode())
    (tmp_path / DUMP_FILE).write_bytes(raw)
    meta = {"sha256": sha or hashlib.sha256(raw).hexdigest(), "source_version": "2026-10-02"}
    (tmp_path / META_FILE).write_text(json.dumps(meta))


def test_load_requires_synced_and_intact_data(tmp_path, monkeypatch):
    with pytest.raises(QuranDataMissingError) as e:
        QuranIndex.load(tmp_path)
    assert "sync_quran_dump" in str(e.value) and e.value.retryable is False
    _write(tmp_path, mushaf_payload(), sha="0" * 64)
    with pytest.raises(QuranDataMissingError):
        QuranIndex.load(tmp_path)
