"""Quranpedia adapter (Task 5a) — official sources only (docs/SOURCE_VALIDATION.md).

Serves (allowlist, locked 2026-10-04):
  * Quran                         — official Mushaf 1 dump (local, versioned, synced)
  * Tafsir al-Muyassar            — book 2012 (live API; covers all 6,236 ayahs)
  * Tafsir Ibn Kathir             — book 136  (live API)
  * Asbab al-Nuzul (al-Wahidi)    — book 2919 (live API; provider author is null)
  * Al-Muharrar fi Asbab al-Nuzul — book 460  (live API)

Live endpoint: GET https://api.quranpedia.net/v1/ayah/{surah}/{ayah}/book/{book_id}
(no auth; 120 req/min, 10,000 req/day per IP). Responses are NOT cached beyond the request.

Traceability (approved): Quranpedia has no passage ids. A passage is identified by its
official address (`/v1/ayah/S/A/book/B`), the provider's volume/page, `retrieved_at` and the
SHA-256 of the exact text. The provider's ayah association (possibly several ayahs) is kept
verbatim. Nothing is invented: missing provider metadata stays missing.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx

from app.core_logging import get_logger
from app.domain.enums import (
    PipelineStage,
    QuranTextForm,
    RetrievalChannel,
    RetrievalMatchBasis,
    RetrievalMethod,
    SourceType,
)
from app.domain.errors import SourceUnavailableError
from app.domain.evidence import (
    AsbabNuzulMetadata,
    AyahRef,
    Evidence,
    QuranMetadata,
    TafsirMetadata,
    text_fingerprint,
)
from app.domain.trusted_sources import Provider, TrustedSourceId, get_trusted_source
from app.sources.base import AdapterConnectionState, SourceHit, SourceQuery, TrustedSourceAdapter
from app.sources.quran_index import QuranAyah, QuranIndex, keyword_tokens

OFFICIAL_BASE_URL = "https://api.quranpedia.net/v1"
USER_AGENT = "Mizan/0.1 (religious-claim verification; live official API use)"
QURAN_TEXT_TRANSFORM = "quranpedia_ayah_text_strip_bom_v1"
PASSAGE_TEXT_TRANSFORM = "quranpedia_html_to_text_v1"

#: Meaning of the provider's `page` value per book, verified from official data:
#: 136 and 460 identify a printed edition (publisher/edition in /book metadata);
#: 2919 has no edition metadata (provider pagination); in 2012 `page` equals the
#: mushaf-wide ayah id (all 6,236 values), i.e. it is not a page number.
PAGE_KIND: dict[int, str] = {136: "printed", 460: "printed", 2919: "provider", 2012: "none"}

_QURAN_ADDR = re.compile(r"^/v1/mushafs/(\d+)/(\d+)/(\d+)$")
_BOOK_ADDR = re.compile(r"^/v1/ayah/(\d+)/(\d+)/book/(\d+)$")
log = get_logger("sources.quranpedia")


class _TextExtractor(HTMLParser):
    _BREAKS = {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._BREAKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BREAKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(raw: str) -> str:
    """Deterministic provider-HTML -> plain text (transform `quranpedia_html_to_text_v1`)."""
    p = _TextExtractor()
    p.feed(raw.replace("\r", ""))
    p.close()
    text = html.unescape("".join(p.parts)).replace("﻿", "")
    lines = [" ".join(line.split()) for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def _overlap_score(query_text: str | None, text: str) -> float | None:
    if not query_text:
        return None
    q = set(keyword_tokens(query_text))
    if not q:
        return None
    return round(len(q & set(keyword_tokens(text))) / len(q), 4)


class QuranpediaAdapter(TrustedSourceAdapter):
    provider = Provider.QURANPEDIA
    served_sources = frozenset(
        {
            TrustedSourceId.QURAN,
            TrustedSourceId.TAFSIR_AL_MUYASSAR,
            TrustedSourceId.TAFSIR_IBN_KATHIR,
            TrustedSourceId.ASBAB_AL_NUZUL_AL_WAHIDI,
            TrustedSourceId.AL_MUHARRAR_FI_ASBAB_AL_NUZUL,
        }
    )

    def __init__(
        self,
        *,
        enabled: bool = True,
        base_url: str | None = None,
        data_dir: Path | None = None,
        quran_index: QuranIndex | None = None,
        timeout_seconds: float = 15,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._enabled = enabled
        self._base_url = (base_url or OFFICIAL_BASE_URL).rstrip("/")
        self._data_dir = data_dir
        self._index = quran_index
        self._timeout = timeout_seconds
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # ------------------------------------------------------------ contract

    @property
    def supported_methods(self) -> frozenset[RetrievalMethod]:
        return frozenset({RetrievalMethod.EXACT, RetrievalMethod.KEYWORD})

    def connection_state(self) -> AdapterConnectionState:
        return (
            AdapterConnectionState.CONFIGURED if self._enabled else AdapterConnectionState.DISABLED
        )

    def quran_index(self) -> QuranIndex:
        """The official Mushaf 1 index (loaded once from the synced local dump)."""
        if self._index is None:
            self._index = QuranIndex.load(self._data_dir)
        return self._index

    async def search(self, query: SourceQuery) -> list[SourceHit]:
        src = get_trusted_source(query.source)
        if query.source not in self.served_sources:
            raise ValueError(f"{query.source.value} is not served by Quranpedia")
        if src.source_type == SourceType.QURAN:
            return self._search_quran(query)
        if query.method != RetrievalMethod.EXACT or query.anchor is None:
            raise ValueError("tafsir/asbab retrieval is ayah-anchored: EXACT with an anchor")
        evidence = await self._fetch_passages(query.source, query.anchor)
        return [
            SourceHit(
                evidence=ev,
                method=RetrievalMethod.EXACT,
                match_basis=query.basis or RetrievalMatchBasis.EXPLICIT_REFERENCE,
                score=_overlap_score(query.query_text, ev.text),
                anchor_ayah=query.anchor,
            )
            for ev in evidence
        ][: query.limit]

    async def get_records(self, source: TrustedSourceId, source_address: str) -> list[Evidence]:
        m = _QURAN_ADDR.match(source_address)
        if m and source == TrustedSourceId.QURAN:
            mushaf, s, a = (int(x) for x in m.groups())
            ayah = self.quran_index().get(s, a)
            if mushaf != self.quran_index().mushaf_id or ayah is None:
                return []
            return [self.quran_evidence(ayah)]
        m = _BOOK_ADDR.match(source_address)
        if m:
            s, a, book = (int(x) for x in m.groups())
            if book != get_trusted_source(source).quranpedia_book_id:
                raise ValueError(f"address {source_address} is not bound to {source.value}")
            ayah = self.quran_index().get(s, a)
            if ayah is None:
                return []
            return await self._fetch_passages(source, ayah.ref)
        raise ValueError(f"not an official Quranpedia address for {source.value}: {source_address}")

    # ------------------------------------------------------------ Quran (official dump)

    def _search_quran(self, query: SourceQuery) -> list[SourceHit]:
        index = self.quran_index()
        hits: list[SourceHit] = []
        if query.ayah_refs:
            for ref in query.ayah_refs:
                ayah = index.get(ref.surah_number, ref.ayah_number)
                if ayah is None or ayah.quranpedia_ayah_id != ref.quranpedia_ayah_id:
                    continue  # never guessed
                hits.append(
                    SourceHit(
                        evidence=self.quran_evidence(ayah),
                        method=query.method,
                        match_basis=query.basis or RetrievalMatchBasis.EXPLICIT_REFERENCE,
                    )
                )
        elif query.method == RetrievalMethod.EXACT and query.query_text:
            for match in index.find_quotes(query.query_text, limit=query.limit):
                for ayah in match.ayahs:
                    hits.append(
                        SourceHit(
                            evidence=self.quran_evidence(ayah),
                            method=RetrievalMethod.EXACT,
                            match_basis=RetrievalMatchBasis.QUOTED_TEXT,
                            score=float(match.matched_words),
                        )
                    )
        elif query.method == RetrievalMethod.KEYWORD and query.query_text:
            for ayah, score in index.keyword_search(query.query_text, limit=query.limit):
                hits.append(
                    SourceHit(
                        evidence=self.quran_evidence(ayah),
                        method=RetrievalMethod.KEYWORD,
                        match_basis=RetrievalMatchBasis.KEYWORD,
                        score=score,
                    )
                )
        return hits[: query.limit]

    def quran_evidence(self, ayah: QuranAyah) -> Evidence:
        index = self.quran_index()
        src = get_trusted_source(TrustedSourceId.QURAN)
        address = f"/v1/mushafs/{index.mushaf_id}/{ayah.surah_number}/{ayah.ayah_number}"
        return Evidence(
            evidence_id=f"mizan-ev:quran:{index.mushaf_id}:{ayah.quranpedia_ayah_id}",
            source_type=SourceType.QURAN,
            text=ayah.text,
            source_name=src.name_ar,
            provider=Provider.QURANPEDIA,
            trusted_source_id=TrustedSourceId.QURAN,
            reference=f"{ayah.surah_name_ar}، الآية {ayah.ayah_number}",
            source_address=address,
            source_url=f"https://api.quranpedia.net{address}",
            source_record_id=str(ayah.quranpedia_ayah_id),
            retrieval_channel=RetrievalChannel.OFFICIAL_DUMP,
            source_version=index.version,
            retrieved_at=self._clock(),
            text_sha256=text_fingerprint(ayah.text),
            text_transform=QURAN_TEXT_TRANSFORM,
            metadata=QuranMetadata(
                mushaf_id=index.mushaf_id,
                quranpedia_ayah_id=ayah.quranpedia_ayah_id,
                surah_number=ayah.surah_number,
                surah_name_ar=ayah.surah_name_ar,
                ayah_number=ayah.ayah_number,
                ayah_text=ayah.text,
                text_form=QuranTextForm.MUSHAF_DIACRITIZED,
                ayah_text_normalized=ayah.normalized,
                dump_version=index.version,
            ),
        )

    # ------------------------------------------------------------ Tafsir / Asbab (live API)

    async def _get_json(self, path: str) -> Any:
        url = f"{self._base_url}{path}"
        stage = PipelineStage.HYBRID_RETRIEVAL
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            ) as client:
                r = await client.get(url)
        except httpx.TimeoutException as exc:
            raise SourceUnavailableError(f"Quranpedia timeout: {path}", stage=stage) from exc
        except httpx.HTTPError as exc:
            raise SourceUnavailableError(
                f"Quranpedia network error ({type(exc).__name__}): {path}", stage=stage
            ) from exc
        if r.status_code == 429:
            raise SourceUnavailableError(f"Quranpedia rate limit (HTTP 429): {path}", stage=stage)
        if r.status_code >= 500:
            raise SourceUnavailableError(f"Quranpedia HTTP {r.status_code}: {path}", stage=stage)
        if r.status_code != 200:
            err = SourceUnavailableError(f"Quranpedia HTTP {r.status_code}: {path}", stage=stage)
            err.retryable = False
            raise err
        try:
            return r.json()
        except ValueError as exc:
            err = SourceUnavailableError(f"Quranpedia returned non-JSON: {path}", stage=stage)
            err.retryable = False
            raise err from exc

    async def _fetch_passages(self, source: TrustedSourceId, anchor: AyahRef) -> list[Evidence]:
        src = get_trusted_source(source)
        book = src.quranpedia_book_id
        if book is None:  # pragma: no cover - policy guarantees a binding
            raise ValueError(f"{source.value} has no Quranpedia book binding")
        index = self.quran_index()
        ayah = index.get(anchor.surah_number, anchor.ayah_number)
        if ayah is None or ayah.quranpedia_ayah_id != anchor.quranpedia_ayah_id:
            raise ValueError("anchor is not a valid ayah of the official Quran source")
        address = f"/v1/ayah/{ayah.surah_number}/{ayah.ayah_number}/book/{book}"
        payload = await self._get_json(address[len("/v1") :])
        retrieved_at = self._clock()

        book_meta = payload.get("book") if isinstance(payload, dict) else None
        content = payload.get("content") if isinstance(payload, dict) else None
        if not isinstance(book_meta, dict) or not isinstance(content, list):
            err = SourceUnavailableError(
                f"unexpected Quranpedia response shape: {address}",
                stage=PipelineStage.HYBRID_RETRIEVAL,
            )
            err.retryable = False
            raise err
        if book_meta.get("id") != book:
            err = SourceUnavailableError(
                f"Quranpedia returned book {book_meta.get('id')!r} for {address}",
                stage=PipelineStage.HYBRID_RETRIEVAL,
            )
            err.retryable = False
            raise err
        book_name = str(book_meta.get("name") or "").strip() or src.name_ar
        author = book_meta.get("author")
        provider_author = (
            str(author.get("ar_name")).strip()
            if isinstance(author, dict) and author.get("ar_name")
            else None
        )

        out: list[Evidence] = []
        skipped = 0
        for pos, item in enumerate(content):
            ev = self._passage_evidence(
                source=source,
                book=book,
                book_name=book_name,
                provider_author=provider_author,
                ayah=ayah,
                address=address,
                item=item,
                position=pos,
                retrieved_at=retrieved_at,
            )
            if ev is None:
                skipped += 1
            else:
                out.append(ev)
        if skipped:
            log.warning("quranpedia: skipped %d untraceable item(s) at %s", skipped, address)
        return out

    def _passage_evidence(
        self,
        *,
        source: TrustedSourceId,
        book: int,
        book_name: str,
        provider_author: str | None,
        ayah: QuranAyah,
        address: str,
        item: Any,
        position: int,
        retrieved_at: datetime,
    ) -> Evidence | None:
        """Build one traceable Evidence record, or None if it cannot be traced."""
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            return None
        text = html_to_text(item["text"])
        raw_assoc = item.get("ayahs")
        if not text or raw_assoc is None or not str(raw_assoc).strip():
            return None
        index = self.quran_index()
        associated: list[AyahRef] = []
        for part in str(raw_assoc).split(","):
            part = part.strip()
            resolved = index.by_id(int(part)) if part.isdigit() else None
            if resolved is None:
                return None  # provider association cannot be resolved -> untraceable
            associated.append(resolved.ref)
        src = get_trusted_source(source)
        part = item.get("part")
        page = item.get("page")
        provider_part = str(part).strip() if part not in (None, "") else None
        provider_page = str(page).strip() if page not in (None, "") else None
        page_kind = PAGE_KIND.get(book, "provider")
        sha = text_fingerprint(text)

        ref_bits = [book_name]
        if page_kind != "none":
            if provider_part:
                ref_bits.append(f"الجزء {provider_part}")
            if provider_page:
                ref_bits.append(f"الصفحة {provider_page}")
        reference = "، ".join(ref_bits) + f" — {ayah.surah_name_ar}، الآية {ayah.ayah_number}"

        common = dict(
            provider_book_id=book,
            provider_book_name=book_name,
            provider_author=provider_author,
            requested_ayah=ayah.ref,
            surah_name_ar=ayah.surah_name_ar,
            associated_ayahs=associated,
            provider_ayah_association=str(raw_assoc).strip(),
            provider_part=provider_part,
            provider_page=provider_page,
            page_kind=page_kind,
            position_in_response=position,
        )
        metadata = (
            TafsirMetadata(**common)
            if src.source_type == SourceType.TAFSIR
            else AsbabNuzulMetadata(**common)
        )
        return Evidence(
            evidence_id=f"mizan-ev:{source.value}:{ayah.surah_number}:{ayah.ayah_number}:{sha[:16]}",
            source_type=src.source_type,
            text=text,
            source_name=src.name_ar,
            provider=Provider.QURANPEDIA,
            trusted_source_id=source,
            reference=reference,
            source_address=address,
            source_url=f"https://api.quranpedia.net{address}",
            source_record_id=None,  # Quranpedia exposes no passage id; none is invented
            retrieval_channel=RetrievalChannel.LIVE_API,
            source_version=None,
            retrieved_at=retrieved_at,
            text_sha256=sha,
            text_transform=PASSAGE_TEXT_TRANSFORM,
            metadata=metadata,
        )
