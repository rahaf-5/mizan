"""Official Mushaf 1 sync: strict checksum, validation, official corrections, atomic install."""

from __future__ import annotations

import copy
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
            return httpx.Response(200, stream=httpx.ByteStream(RAW))
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


NEWER = dict(FULL, license={"version": "2026-10-04"})
RAW_NEWER = gzip.compress(json.dumps(NEWER, ensure_ascii=False).encode())
SHA_NEWER = hashlib.sha256(RAW_NEWER).hexdigest()
STALE_MANIFEST = {
    "version": "2026-10-02",
    "generated_at": "2026-10-02T03:32:23+00:00",
    "files": [
        {
            "name": DUMP_FILE,
            "sha256": SHA,
            "bytes": len(RAW),
            "built_at": "2026-10-02T03:31:37+00:00",
        }
    ],
}


def api_doc():
    doc = copy.deepcopy(FULL)
    doc.pop("license")
    return doc  # GET /v1/mushafs/1 shape: {id, name, surahs:[{id, name, ayahs:[...]}]}


def stale_transport(api=None, api_status=200, raw=RAW_NEWER, seen=None):
    def handler(r: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(r.url.path)
        if r.url.path == "/dumps/manifest.json":
            return httpx.Response(200, json=STALE_MANIFEST)
        if r.url.path == f"/dumps/{DUMP_FILE}":
            return httpx.Response(
                200,
                stream=httpx.ByteStream(raw),
                headers={"last-modified": "Sun, 04 Oct 2026 03:31:26 GMT"},
            )
        if r.url.path == "/v1/mushafs/1":
            return httpx.Response(api_status, json=api if api is not None else api_doc())
        if r.url.path == "/v1/changes":
            return httpx.Response(
                200, json={"changes": {"ayahs": {"truncated": False, "rows": []}}}
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


async def test_newer_dump_is_installed_only_after_full_official_api_crosscheck(tmp_path):
    seen: list[str] = []
    meta = await sync_quran_dump(
        data_dir=tmp_path, transport=stale_transport(seen=seen), out=lambda _: None, now=NOW
    )
    v = meta["verification"]
    assert v["method"] == "official_api_crosscheck" and v["ayahs_compared"] == 6236
    assert v["downloaded_sha256"] == SHA_NEWER == meta["sha256"]  # recorded, not hardcoded
    assert v["stale_manifest_sha256"] == SHA and v["stale_manifest_version"] == "2026-10-02"
    assert v["dump_embedded_version"] == "2026-10-04" and v["verified_at"].startswith("2026-10-04")
    assert v["api_url"] == "https://api.quranpedia.net/v1/mushafs/1"
    assert meta["dump_version"] == "2026-10-04"
    assert "/v1/mushafs/1" in seen
    assert QuranIndex.load(tmp_path).version == "2026-10-04"


def _mutate(fn):
    doc = api_doc()
    fn(doc)
    return doc


def _set_text(doc):
    doc["surahs"][1]["ayahs"][254]["text"] = "نص مختلف"


def _drop(doc):
    doc["surahs"][2]["ayahs"].pop()


def _extra(doc):
    doc["surahs"][2]["ayahs"].append({"id": 999999, "number": 99999, "text": "زائد"})


def _wrong_mushaf(doc):
    doc["id"] = 2


def _diacritic_only(doc):  # exact comparison: even a diacritic difference fails closed
    doc["surahs"][0]["ayahs"][0]["text"] = doc["surahs"][0]["ayahs"][0]["text"].replace("ِ", "", 1)


def _wrong_id(doc):
    doc["surahs"][0]["ayahs"][0]["id"] = 424242


@pytest.mark.parametrize(
    "mutation", [_set_text, _drop, _extra, _wrong_mushaf, _diacritic_only, _wrong_id]
)
async def test_any_api_difference_refuses_installation(tmp_path, mutation):
    with pytest.raises(SyncError):
        await sync_quran_dump(
            data_dir=tmp_path, transport=stale_transport(api=_mutate(mutation)), out=lambda _: None
        )
    assert not (tmp_path / DUMP_FILE).exists() and not (tmp_path / META_FILE).exists()


async def test_api_failure_refuses_installation(tmp_path):
    with pytest.raises(SyncError):
        await sync_quran_dump(
            data_dir=tmp_path, transport=stale_transport(api_status=500), out=lambda _: None
        )
    assert not (tmp_path / DUMP_FILE).exists()


async def test_mismatch_without_newer_dump_never_uses_the_fallback(tmp_path):
    same_version = gzip.compress(
        json.dumps(dict(FULL, license={"version": "2026-10-02"}), ensure_ascii=False).encode()
        + b" "
    )
    seen: list[str] = []
    with pytest.raises(SyncError) as e:
        await sync_quran_dump(
            data_dir=tmp_path,
            transport=stale_transport(raw=same_version, seen=seen),
            out=lambda _: None,
        )
    assert "not installed" in str(e.value) and "/v1/mushafs/1" not in seen
    assert not (tmp_path / DUMP_FILE).exists()


async def test_normal_path_records_manifest_verification(tmp_path):
    meta = await sync_quran_dump(
        data_dir=tmp_path, transport=transport(rows=[]), out=lambda _: None
    )
    assert meta["verification"]["method"] == "official_manifest_sha256"
    assert meta["verification"]["downloaded_sha256"] == SHA


async def test_checksum_is_computed_over_served_bytes_not_transparently_decoded(tmp_path):
    def handler(r: httpx.Request) -> httpx.Response:
        if r.url.path == f"/dumps/{DUMP_FILE}":
            # A server that labels the .gz with Content-Encoding: gzip must not change the hash.
            return httpx.Response(
                200, stream=httpx.ByteStream(RAW), headers={"content-encoding": "gzip"}
            )
        return transport(rows=[]).handler(r)

    meta = await sync_quran_dump(
        data_dir=tmp_path, transport=httpx.MockTransport(handler), out=lambda _: None
    )
    assert meta["sha256"] == SHA
