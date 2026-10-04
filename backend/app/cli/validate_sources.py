"""Live SOURCE INTEGRATION VALIDATION — official Quranpedia API + official Dorar API.

    cd backend && source .venv/bin/activate && python -m app.cli.validate_sources

Read-only research tool (pre-Task 5). It sends a small, FIXED list of public
requests (well-known ayahs / one well-known hadith phrase) to the two official
endpoints only, and prints the STRUCTURE of each response: keys, value types,
short value previews, and traceability checks. It never sends Mizan user content,
needs no credentials, reads no .env value, and stores nothing.

Official sources:
  Quranpedia API docs  https://quranpedia.net/api-docs   (base https://api.quranpedia.net/v1;
                       no auth; 120 req/min and 10,000 req/day per IP)
  Dorar API page       https://dorar.net/article/389     (https://dorar.net/dorar_api.json?skey=)

~22 requests with a pause between them — far below the documented limits.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote

import httpx

QURANPEDIA_BASE = "https://api.quranpedia.net/v1"
DORAR_API = "https://dorar.net/dorar_api.json"
USER_AGENT = "Mizan-source-validation/0.1 (read-only; pre-integration check)"

#: Book ids discovered through the official API (category 11 listing, embed
#: fragments) — this script re-checks each one live via GET /book/{id}.
CANDIDATE_BOOKS: dict[str, tuple[int, ...]] = {
    "tafsir_al_muyassar": (2012, 32),
    "tafsir_ibn_kathir": (136, 331),
    "asbab_al_nuzul_al_wahidi": (2919, 235),
    "al_muharrar_fi_asbab_al_nuzul": (460,),
}

#: (label, path) — fixed public requests only.
QURANPEDIA_REQUESTS: tuple[tuple[str, str], ...] = (
    ("ayah options 2:255", "/ayah/2/255/options"),
    ("mushaf 1 ayah 2:255", "/mushafs/1/2/255"),
    ("mushaf 2 ayah 2:255", "/mushafs/2/2/255"),
    ("surah information 2", "/surah/information/2"),
    *((f"book {b}", f"/book/{b}") for ids in CANDIDATE_BOOKS.values() for b in ids),
    ("muyassar 2012 @ 2:255", "/ayah/2/255/book/2012"),
    ("muyassar 32 @ 2:255", "/ayah/2/255/book/32"),
    ("ibn kathir 136 @ 2:255", "/ayah/2/255/book/136"),
    ("ibn kathir 331 @ 2:255", "/ayah/2/255/book/331"),
    ("ibn kathir 136 @ 2:2 (grouped ayahs?)", "/ayah/2/2/book/136"),
    ("wahidi 2919 @ 2:158", "/ayah/2/158/book/2919"),
    ("wahidi 235 @ 2:158", "/ayah/2/158/book/235"),
    ("muharrar 460 @ 2:158", "/ayah/2/158/book/460"),
)
DORAR_SAMPLE = "إنما الأعمال بالنيات"  # well-known public hadith phrase

DORAR_LABELS = ("الراوي", "المحدث", "المصدر", "الصفحة أو الرقم", "خلاصة حكم المحدث")
_HTML_TAG = re.compile(r"<[^>]+>")
_ID_KEY = re.compile(r"(^|_)(id|uuid|key|slug)$", re.I)


# ---------------------------------------------------------------- structure


def describe(value: Any, depth: int = 0, max_depth: int = 4) -> Any:
    """Shape of a JSON value: keys, types and short previews (no full texts)."""
    if isinstance(value, dict):
        if depth >= max_depth:
            return f"<object: {len(value)} keys>"
        return {k: describe(v, depth + 1, max_depth) for k, v in value.items()}
    if isinstance(value, list):
        if not value:
            return "<array: 0 items>"
        return {f"<array: {len(value)} items> first": describe(value[0], depth + 1, max_depth)}
    if isinstance(value, str):
        preview = value[:60].replace("\n", "\\n")
        return f"<str {len(value)} chars> {preview!r}"
    return value


def text_checks(text: str) -> dict[str, Any]:
    """Facts about a returned Arabic text (encoding/markup), for schema mapping."""
    return {
        "chars": len(text),
        "starts_with_BOM_U+FEFF": text.startswith("﻿"),
        "contains_BOM": "﻿" in text,
        "contains_html_tags": bool(_HTML_TAG.search(text)),
        "has_tashkeel": bool(re.search(r"[ً-ْ]", text)),
        "has_alef_wasla_U+0671 (Uthmani rasm marker)": "ٱ" in text,
        "has_dagger_alef_U+0670": "ٰ" in text,
        "has_quranic_waqf_marks_U+06D6-06DC": bool(re.search(r"[ۖ-ۜ]", text)),
    }


def id_like_keys(obj: Any) -> list[str]:
    if isinstance(obj, dict):
        return sorted(k for k in obj if _ID_KEY.search(k))
    return []


def analyse_quranpedia(path: str, payload: Any) -> list[str]:
    notes: list[str] = []
    if isinstance(payload, dict) and isinstance(payload.get("text"), str):
        notes.append(f"text checks: {text_checks(payload['text'])}")
    if isinstance(payload, dict) and isinstance(payload.get("content"), list):
        items = payload["content"]
        notes.append(f"content items: {len(items)}")
        if items:
            keys = sorted({k for it in items if isinstance(it, dict) for k in it})
            notes.append(f"content item keys (union): {keys}")
            notes.append(f"content item id-like keys: {id_like_keys(items[0]) or 'NONE'}")
            notes.append(f"'ayahs' values: {[it.get('ayahs') for it in items][:10]}")
            locs = [(it.get("part"), it.get("page"), it.get("ayahs")) for it in items]
            notes.append(f"(part, page, ayahs) unique across items: {len(set(locs)) == len(locs)}")
            first = items[0].get("text")
            if isinstance(first, str):
                notes.append(f"first content text checks: {text_checks(first)}")
        book = payload.get("book")
        if isinstance(book, dict):
            notes.append(f"book.author: {describe(book.get('author'))}")
    if path.startswith("/book/") and isinstance(payload, dict):
        notes.append(
            "book: type={!r} relative_ayah_service={!r} category={!r} author={!r}".format(
                payload.get("type"),
                payload.get("relative_ayah_service"),
                (payload.get("category") or {}).get("name"),
                (payload.get("author") or {}).get("ar_name") if payload.get("author") else None,
            )
        )
    return notes


# ---------------------------------------------------------------- Dorar HTML


@dataclass
class DorarBlock:
    hadith_text: str = ""
    fields: dict[str, str] = field(default_factory=dict)


class _DorarParser(HTMLParser):
    """Tolerant parser for Dorar's result HTML (it contains unbalanced </span>)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[DorarBlock] = []
        self.hrefs: list[str] = []
        self.attr_names: set[str] = set()
        self._mode: str | None = None
        self._label: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        self.attr_names.update(k for k, _ in attrs)
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"] or "")
        cls = a.get("class") or ""
        if tag == "div" and cls == "hadith":
            self.blocks.append(DorarBlock())
            self._mode, self._buf = "hadith", []
        elif tag == "div" and cls == "hadith-info":
            self._flush_field()
            self._mode, self._label, self._buf = "info", None, []
        elif tag == "span" and cls == "info-subtitle" and self._mode == "info":
            self._flush_field()
            self._mode = "label"
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self._mode == "hadith" and self.blocks:
            self.blocks[-1].hadith_text = " ".join("".join(self._buf).split())
            self._mode = None
        elif tag == "span" and self._mode == "label":
            self._label = "".join(self._buf).strip().rstrip(":").strip()
            self._mode, self._buf = "info", []
        elif tag == "div" and self._mode == "info":
            self._flush_field()
            self._mode = None

    def handle_data(self, data: str) -> None:
        if self._mode in {"hadith", "label", "info"}:
            self._buf.append(data)

    def _flush_field(self) -> None:
        if self._mode == "info" and self._label and self.blocks:
            self.blocks[-1].fields[self._label] = " ".join("".join(self._buf).split())
        self._label, self._buf = None, []


def parse_dorar_result(html: str) -> _DorarParser:
    p = _DorarParser()
    p.feed(html)
    p.close()
    return p


def analyse_dorar(content_type: str, raw: str) -> list[str]:
    notes = [f"content-type: {content_type}", f"body starts: {raw[:40]!r}"]
    try:
        payload = json.loads(raw)
    except ValueError:
        return [*notes, "NOT plain JSON (JSONP or HTML?) — stop: unexpected format"]
    notes.append(f"top-level structure: {describe(payload, max_depth=2)}")
    html = ((payload or {}).get("ahadith") or {}).get("result")
    if not isinstance(html, str):
        return [*notes, "no ahadith.result string"]
    p = parse_dorar_result(html)
    notes.append(f"result HTML length: {len(html)}; result blocks: {len(p.blocks)}")
    notes.append(f"all hrefs: {p.hrefs}")
    notes.append(f"all HTML attribute names used: {sorted(p.attr_names)}")
    notes.append(
        "per-hadith id/data-* attribute present: "
        f"{any(n == 'id' or n.startswith('data-') for n in p.attr_names)}"
    )
    for i, b in enumerate(p.blocks[:3], 1):
        missing = [lab for lab in DORAR_LABELS if lab not in b.fields]
        notes.append(
            f"block {i}: text={b.hadith_text[:80]!r} fields={b.fields} missing_labels={missing}"
        )
    complete = sum(all(lab in b.fields for lab in DORAR_LABELS) for b in p.blocks)
    notes.append(f"blocks with all 5 labels: {complete}/{len(p.blocks)}")
    notes.append(
        f"blocks whose text contains '. . .' or '...': "
        f"{sum(('. . .' in b.hadith_text) or ('...' in b.hadith_text) for b in p.blocks)}"
    )
    return notes


# ---------------------------------------------------------------- runner


async def run_validation(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    delay: float = 0.7,
    out: Callable[[str], None] = print,
) -> int:
    failures = 0
    async with httpx.AsyncClient(
        timeout=30, transport=transport, headers={"User-Agent": USER_AGENT}
    ) as client:
        out("=== QURANPEDIA (official API, no auth) ===")
        for label, path in QURANPEDIA_REQUESTS:
            url = f"{QURANPEDIA_BASE}{path}"
            try:
                r = await client.get(url)
            except httpx.HTTPError as exc:
                failures += 1
                out(f"\n[{label}] GET {url} -> NETWORK ERROR {type(exc).__name__}")
                continue
            out(f"\n[{label}] GET {url} -> HTTP {r.status_code} ({r.headers.get('content-type')})")
            for h in ("x-ratelimit-limit", "x-ratelimit-remaining", "retry-after"):
                if h in r.headers:
                    out(f"  header {h}: {r.headers[h]}")
            if r.status_code != 200:
                failures += 1
                out(f"  body: {r.text[:300]!r}")
            else:
                payload = r.json()
                out("  structure: " + json.dumps(describe(payload), ensure_ascii=False))
                for note in analyse_quranpedia(path, payload):
                    out("  - " + note)
            await asyncio.sleep(delay)

        out("\n=== DORAR AL-SUNNIYAH (official dorar_api.json) ===")
        url = f"{DORAR_API}?skey={quote(DORAR_SAMPLE)}"
        try:
            r = await client.get(url)
            out(f"[hadith search] GET {url} -> HTTP {r.status_code}")
            if r.status_code != 200:
                failures += 1
                out(f"  body: {r.text[:300]!r}")
            else:
                for note in analyse_dorar(r.headers.get("content-type", ""), r.text):
                    out("  - " + note)
        except httpx.HTTPError as exc:
            failures += 1
            out(f"[hadith search] GET {url} -> NETWORK ERROR {type(exc).__name__}")

    out(f"\nDone. failed requests: {failures}")
    return 0 if failures == 0 else 1


def main() -> int:
    return asyncio.run(run_validation())


if __name__ == "__main__":
    sys.exit(main())
