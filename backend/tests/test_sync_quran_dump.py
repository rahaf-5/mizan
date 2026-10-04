"""Official Mushaf 1 sync: strict checksum, validation, official corrections, atomic install."""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timezone

import httpx
import pytest

from app.cli.sync_quran_dump import SyncError, sync_quran_dump
from app.sources.quran_index import DUMP_FILE, META_FILE, PATCH_FILE, QuranIndex
from tests.quran_fixture import mushaf_payload

FULL = mushaf_payload(extra_surah_ayahs=6236 - 267)  # 6,236 ayahs like the real Mushaf
RAW = gzip.compress(json.dumps(FULL, ensure_ascii=False).encode())
SHA = hashlib.sha256(RAW).hexdigest()
NOW = lambda: datetime(2026, 10, 4, tzinfo=timezone.utc)  # noqa: E731


def transport(*, sha=SHA, truncated=False, rows=None, seen=None):
    rows = (
        rows
        if rows is not None
        else [
            {
                "mushaf": 1,
                "surah": "2",
                "ayah": 255,
                "changed_at": "2026-10-03",
                "refetch": "/v1/mushafs/1/2/255",
            },
            {
                "mushaf": 4,
                "surah": "1",
                "ayah": 1,
                "changed_at": "2026-10-03",
                "refetch": "/v1/mushafs/4/1/1",
            },
        ]
    )

    def handler(r: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(str(r.url))
        if r.url.path == "/dumps/manifest.json":
            return httpx.Response(
                200, json={"version": "2026-10-02", "files": [{"name": DUMP_FILE, "sha256": sha}]}
            )
        if r.url.path == f"/dumps/{DUMP_FILE}":
            return httpx.Response(200, content=RAW)
        if r.url.path == "/v1/changes":
            assert r.url.params["since"] == "2026-10-02"
            return httpx.Response(
                200,
                json={
                    "changes": {"ayahs": {"count": len(rows), "truncated": truncated, "rows": rows}}
                },
            )
        if r.url.path == "/v1/mushafs/1/2/255":
            return httpx.Response(200, json={"id": 262, "number": 255, "text": "﻿نص مصحح"})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


async def test_sync_installs_verified_dump_and_applies_official_corrections(tmp_path):
    seen: list[str] = []
    meta = await sync_quran_dump(
        data_dir=tmp_path, transport=transport(seen=seen), out=lambda _: None, now=NOW
    )
    assert meta["sha256"] == SHA and meta["changes_applied"] == 1
    assert meta["source_version"] == "2026-10-02+changes@2026-10-04"
    assert {httpx.URL(u).host for u in seen} == {"quranpedia.net", "api.quranpedia.net"}
    assert not any("/mushafs/4/" in u for u in seen)  # only Mushaf 1 corrections
    index = QuranIndex.load(tmp_path)
    assert index.get(2, 255).text == "نص مصحح" and index.version == meta["source_version"]
    assert json.loads((tmp_path / PATCH_FILE).read_text())[0]["surah"] == 2


async def test_checksum_mismatch_is_refused_and_nothing_installed(tmp_path):
    with pytest.raises(SyncError):
        await sync_quran_dump(
            data_dir=tmp_path, transport=transport(sha="0" * 64), out=lambda _: None
        )
    assert not (tmp_path / DUMP_FILE).exists() and not (tmp_path / META_FILE).exists()


async def test_truncated_change_list_is_refused(tmp_path):
    with pytest.raises(SyncError):
        await sync_quran_dump(
            data_dir=tmp_path, transport=transport(truncated=True), out=lambda _: None
        )
    assert not (tmp_path / DUMP_FILE).exists()


async def test_no_corrections_keeps_plain_dump_version(tmp_path):
    meta = await sync_quran_dump(
        data_dir=tmp_path, transport=transport(rows=[]), out=lambda _: None
    )
    assert meta["source_version"] == "2026-10-02" and meta["changes_applied"] == 0
