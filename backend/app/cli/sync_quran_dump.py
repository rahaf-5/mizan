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
import re
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
    TOTAL_AYAHS,
    QuranIndex,
    _find_mushaf,
    clean_ayah_text,
)
from app.sources.quranpedia import OFFICIAL_BASE_URL, USER_AGENT

DUMPS_BASE = "https://quranpedia.net/dumps"


class SyncError(RuntimeError):
    pass


def embedded_version(raw: bytes) -> str | None:
    """The `license.version` the provider wrote inside a gzip dump (None if unreadable)."""
    if raw[:2] != b"\x1f\x8b":
        return None
    try:
        lic = json.loads(gzip.decompress(raw)).get("license") or {}
    except (OSError, ValueError, AttributeError):
        return None
    v = lic.get("version") if isinstance(lic, dict) else None
    return str(v).strip() if v else None


def served_is_newer(manifest: dict, entry: dict, version: str | None) -> bool:
    """True only if the dump's own version is a date strictly after the manifest entry."""
    listed = str(entry.get("built_at") or manifest.get("version") or "")[:10]
    return bool(
        version
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}", version[:10])
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}", listed)
        and version[:10] > listed
    )


def _ayah_table(payload: Any) -> tuple[int | None, dict[tuple[int, int], tuple[int, str, str]]]:
    """(mushaf id, {(surah, ayah): (quranpedia id, surah name, text)}) from a mushaf document.

    Only the provider-format normalisation applied everywhere in Mizan: BOM removed and
    surrounding whitespace stripped. No other normalisation, no fuzzy matching.
    """
    mushaf = _find_mushaf(payload)
    if mushaf is None:
        raise SyncError("no mushaf document (surahs list) found")
    table: dict[tuple[int, int], tuple[int, str, str]] = {}
    for surah in mushaf.get("surahs") or []:
        s = int(surah["id"])
        name = str(surah.get("name") or "").strip()
        for a in surah.get("ayahs") or []:
            key = (s, int(a["number"]))
            if key in table:
                raise SyncError(f"duplicate ayah {key[0]}:{key[1]}")
            table[key] = (int(a["id"]), name, clean_ayah_text(str(a.get("text") or "")))
    mid = mushaf.get("id")
    return (int(mid) if mid is not None else None), table


def crosscheck_against_api(dump_payload: Any, api_payload: Any) -> int:
    """Exact comparison of the WHOLE candidate dump with the official API. Fails closed."""
    dump_id, dump = _ayah_table(dump_payload)
    api_id, api = _ayah_table(api_payload)
    if api_id != MUSHAF_ID or dump_id not in (None, MUSHAF_ID):
        raise SyncError(f"mushaf identity mismatch (dump={dump_id}, api={api_id})")
    if len(api) != TOTAL_AYAHS or len(dump) != TOTAL_AYAHS:
        raise SyncError(f"ayah count mismatch (dump={len(dump)}, api={len(api)}, expected 6236)")
    missing, extra = sorted(api.keys() - dump.keys()), sorted(dump.keys() - api.keys())
    if missing or extra:
        raise SyncError(f"ayah set mismatch: missing={missing[:5]} extra={extra[:5]}")
    diffs = [k for k in sorted(api) if api[k] != dump[k]]
    if diffs:
        s, a = diffs[0]
        what = [
            f
            for f, x, y in zip(("id", "surah name", "text"), api[(s, a)], dump[(s, a)], strict=True)
            if x != y
        ]
        raise SyncError(
            f"{len(diffs)} ayah(s) differ from the official API; first {s}:{a} ({', '.join(what)})"
        )
    return len(api)


def describe_mismatch(
    manifest: dict, entry: dict, raw: bytes, actual: str, headers: dict, final_url: str
) -> str:
    """Diagnostics only (nothing is installed): why the served file differs from the manifest."""
    is_gzip = raw[:2] == b"\x1f\x8b"
    embedded = embedded_version(raw)
    lines = [
        f"  manifest: version={manifest.get('version')} "
        f"generated_at={manifest.get('generated_at')}",
        f"  manifest entry: bytes={entry.get('bytes')} built_at={entry.get('built_at')} "
        f"sha256={entry.get('sha256')}",
        f"  served file: url={final_url} bytes={len(raw)} sha256={actual} "
        f"gzip_magic={is_gzip} embedded_version={embedded}",
        f"  served headers: {headers}",
    ]
    if served_is_newer(manifest, entry, embedded):
        lines.append(
            "  diagnosis: the served dump is NEWER than the manifest entry (stale official "
            "manifest). Integrity cannot be verified against the manifest."
        )
    elif headers.get("content-encoding"):
        lines.append("  diagnosis: transfer encoding present; bytes compared as served.")
    return "\n".join(lines)


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
        # Read the exact bytes served (iter_raw: no transparent Content-Encoding decoding),
        # so the checksum is computed over the same file the manifest describes.
        async with client.stream("GET", f"{DUMPS_BASE}/{DUMP_FILE}") as r:
            if r.status_code != 200:
                raise SyncError(f"{DUMP_FILE}: HTTP {r.status_code}")
            raw = b"".join([chunk async for chunk in r.aiter_raw()])
            headers = {
                k: r.headers.get(k)
                for k in (
                    "content-type",
                    "content-encoding",
                    "content-length",
                    "last-modified",
                    "etag",
                )
            }
            final_url = str(r.url)
        actual = hashlib.sha256(raw).hexdigest()
        verification: dict[str, Any] = {
            "method": "official_manifest_sha256",
            "manifest_version": manifest.get("version"),
            "manifest_sha256": entry.get("sha256"),
        }
        if actual != entry.get("sha256"):
            manifest, entry = await manifest_entry()  # manifest may have been rebuilt
        if actual != entry.get("sha256"):
            diagnostics = describe_mismatch(manifest, entry, raw, actual, headers, final_url)
            version = embedded_version(raw)
            official_url = final_url == f"{DUMPS_BASE}/{DUMP_FILE}"
            if not (official_url and served_is_newer(manifest, entry, version)):
                raise SyncError(
                    f"{DUMP_FILE} SHA-256 does not match the official manifest; not installed.\n"
                    + diagnostics
                )
            # Approved fallback: stale official manifest -> verify the WHOLE dump against the
            # official API (GET /v1/mushafs/1). Any difference fails closed.
            out(diagnostics)
            out("stale official manifest -> verifying the dump against the official API ...")
            api_url = f"{OFFICIAL_BASE_URL}/mushafs/{MUSHAF_ID}"
            ra = await client.get(api_url)
            if ra.status_code != 200:
                raise SyncError(f"official API {api_url}: HTTP {ra.status_code}; not installed")
            try:
                api_payload = ra.json()
                dump_payload = json.loads(gzip.decompress(raw))
            except (OSError, ValueError) as exc:
                raise SyncError(
                    f"unreadable data during cross-check; not installed ({exc})"
                ) from exc
            try:
                compared = crosscheck_against_api(dump_payload, api_payload)
            except (KeyError, TypeError, ValueError) as exc:
                raise SyncError(
                    f"malformed data during cross-check; not installed ({exc})"
                ) from exc
            verification = {
                "method": "official_api_crosscheck",
                "api_url": api_url,
                "ayahs_compared": compared,
                "stale_manifest_version": manifest.get("version"),
                "stale_manifest_generated_at": manifest.get("generated_at"),
                "stale_manifest_sha256": entry.get("sha256"),
                "stale_manifest_built_at": entry.get("built_at"),
                "dump_last_modified": headers.get("last-modified"),
            }
            out(f"official API cross-check passed: {compared} ayahs identical")
        verification["verified_at"] = clock().isoformat()
        verification["downloaded_sha256"] = actual
        payload = json.loads(gzip.decompress(raw))
        license_block = payload.get("license") if isinstance(payload, dict) else None
        dump_version = str(
            (license_block or {}).get("version") or manifest.get("version") or ""
        ).strip()
        if not dump_version:
            raise SyncError("dump version not stated by the provider")
        QuranIndex.from_payload(payload, version=dump_version)  # full validation
        verification["dump_embedded_version"] = dump_version
        out(f"dump {DUMP_FILE}: version {dump_version}, verified by {verification['method']}")

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
        "verification": verification,
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
