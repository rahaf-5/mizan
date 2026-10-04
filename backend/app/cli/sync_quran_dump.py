"""Download / update the official Quranpedia Mushaf 1 dump (approved MVP Quran source).

    cd backend && source .venv/bin/activate && python -m app.cli.sync_quran_dump

1. Reads the official manifest (https://quranpedia.net/dumps/manifest.json).
2. Downloads `mushafs-1.json.gz` and verifies its SHA-256 against the manifest
   (strict; the manifest is re-read once if they differ).
3. Validates the data (114 surahs, 6,236 ayahs, unique ids).
4. Applies official corrections since the dump version via
   `GET https://api.quranpedia.net/v1/changes?since=` (refetching each changed Mushaf 1 ayah).
   A truncated change list is refused (completeness cannot be guaranteed).
5. Writes atomically to `backend/data/quranpedia/` (git-ignored; never committed).

Use inside the app needs no attribution per the Quranpedia license; the data is NOT
republished.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import os
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.sources.quran_index import (
    DEFAULT_DATA_DIR,
    DUMP_FILE,
    META_FILE,
    MUSHAF_ID,
    PATCH_FILE,
    QuranIndex,
    clean_ayah_text,
)
from app.sources.quranpedia import OFFICIAL_BASE_URL, USER_AGENT

DUMPS_BASE = "https://quranpedia.net/dumps"


class SyncError(RuntimeError):
    pass


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


async def sync_quran_dump(
    *,
    data_dir: Path | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    out: Callable[[str], None] = print,
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    d = Path(data_dir or DEFAULT_DATA_DIR)
    d.mkdir(parents=True, exist_ok=True)
    clock = now or (lambda: datetime.now(timezone.utc))
    async with httpx.AsyncClient(
        timeout=120, transport=transport, headers={"User-Agent": USER_AGENT}
    ) as client:

        async def manifest_entry() -> tuple[dict, dict]:
            r = await client.get(f"{DUMPS_BASE}/manifest.json")
            if r.status_code != 200:
                raise SyncError(f"manifest: HTTP {r.status_code}")
            manifest = r.json()
            for f in manifest.get("files", []):
                if isinstance(f, dict) and f.get("name") == DUMP_FILE:
                    return manifest, f
            raise SyncError(f"{DUMP_FILE} is not listed in the official manifest")

        manifest, entry = await manifest_entry()
        r = await client.get(f"{DUMPS_BASE}/{DUMP_FILE}")
        if r.status_code != 200:
            raise SyncError(f"{DUMP_FILE}: HTTP {r.status_code}")
        raw = r.content
        actual = hashlib.sha256(raw).hexdigest()
        if actual != entry.get("sha256"):
            manifest, entry = await manifest_entry()  # manifest may have been rebuilt
            if actual != entry.get("sha256"):
                raise SyncError(
                    f"{DUMP_FILE} SHA-256 does not match the official manifest; not installed"
                )
        payload = json.loads(gzip.decompress(raw))
        license_block = payload.get("license") if isinstance(payload, dict) else None
        dump_version = str(
            (license_block or {}).get("version") or manifest.get("version") or ""
        ).strip()
        if not dump_version:
            raise SyncError("dump version not stated by the provider")
        QuranIndex.from_payload(payload, version=dump_version)  # full validation
        out(f"dump {DUMP_FILE}: version {dump_version}, sha256 verified, 6236 ayahs")

        # Official corrections since the dump version.
        r = await client.get(f"{OFFICIAL_BASE_URL}/changes", params={"since": dump_version})
        if r.status_code != 200:
            raise SyncError(f"changes: HTTP {r.status_code}")
        block = (r.json().get("changes") or {}).get("ayahs") or {}
        if block.get("truncated"):
            raise SyncError(
                "official change list is truncated; completeness cannot be guaranteed "
                "(retry later when a newer dump is published)"
            )
        rows = [row for row in block.get("rows") or [] if int(row.get("mushaf", -1)) == MUSHAF_ID]
        patches: list[dict] = []
        for row in rows:
            s, a = int(row["surah"]), int(row["ayah"])
            rr = await client.get(f"{OFFICIAL_BASE_URL}/mushafs/{MUSHAF_ID}/{s}/{a}")
            if rr.status_code != 200:
                raise SyncError(f"refetch {s}:{a}: HTTP {rr.status_code}")
            text = clean_ayah_text(str(rr.json().get("text") or ""))
            if not text:
                raise SyncError(f"refetch {s}:{a}: empty text")
            patches.append(
                {"surah": s, "ayah": a, "text": text, "changed_at": row.get("changed_at")}
            )
        synced_at = clock()
        source_version = dump_version + (
            f"+changes@{synced_at.date().isoformat()}" if patches else ""
        )
        QuranIndex.from_payload(payload, version=source_version, patches=patches)

    meta = {
        "provider": "quranpedia",
        "mushaf_id": MUSHAF_ID,
        "dump_file": DUMP_FILE,
        "dump_url": f"{DUMPS_BASE}/{DUMP_FILE}",
        "dump_version": dump_version,
        "manifest_version": manifest.get("version"),
        "sha256": actual,
        "changes_since": dump_version,
        "changes_applied": len(patches),
        "source_version": source_version,
        "synced_at": synced_at.isoformat(),
    }
    _atomic_write(d / DUMP_FILE, raw)
    _atomic_write(d / PATCH_FILE, json.dumps(patches, ensure_ascii=False).encode("utf-8"))
    _atomic_write(d / META_FILE, json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8"))
    out(f"corrections applied: {len(patches)}; installed version {source_version} in {d}")
    return meta


def main() -> int:
    try:
        asyncio.run(sync_quran_dump())
    except (SyncError, httpx.HTTPError, ValueError) as exc:
        print(f"SYNC FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
