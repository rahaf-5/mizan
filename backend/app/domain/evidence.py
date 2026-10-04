"""Unified Evidence Data Schema (spec §4).

Every Evidence record must be traceable:
Evidence -> Scientific Source -> Provider -> Original Record/Chunk -> Reference/Source URL.
Evidence may only come from the Trusted Sources Allowlist, and its metadata must
match its source_type. Evidence records are produced by trusted-source adapters
from verified source metadata — never by an LLM.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.domain.enums import (
    AsbabRelationType,
    QuranTextForm,
    RetrievalChannel,
    SourceType,
)
from app.domain.errors import UntrustedSourceError
from app.domain.trusted_sources import Provider, TrustedSourceId, get_trusted_source

NonEmptyStr = Annotated[str, Field(min_length=1)]
SurahNumber = Annotated[int, Field(ge=1, le=114)]
AyahNumber = Annotated[int, Field(ge=1)]
#: Quranpedia's mushaf-wide ayah number (2:255 -> 262 in Mushaf 1).
QuranpediaAyahId = Annotated[int, Field(ge=1)]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def text_fingerprint(text: str) -> str:
    """Exact-text fingerprint (SHA-256 of the UTF-8 text) used for traceability."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class AyahRef(BaseModel):
    """One ayah, resolved against the official Quran source (never guessed)."""

    model_config = ConfigDict(frozen=True)

    surah_number: SurahNumber
    ayah_number: AyahNumber
    quranpedia_ayah_id: QuranpediaAyahId


class QuranMetadata(BaseModel):
    """Quran evidence metadata (approved 2026-10-04).

    The MVP text comes from Quranpedia Mushaf 1 — fully diacritized, matching the
    printed King Fahd Complex mushaf, but NOT Uthmani rasm. It is therefore stored
    as `ayah_text` with an explicit `text_form`, never as an "Uthmani" field.
    """

    model_config = ConfigDict(frozen=True)

    source_type: Literal[SourceType.QURAN] = SourceType.QURAN
    mushaf_id: Annotated[int, Field(ge=1)]
    quranpedia_ayah_id: QuranpediaAyahId
    surah_number: SurahNumber
    surah_name_ar: NonEmptyStr
    ayah_number: AyahNumber
    ayah_text: NonEmptyStr
    text_form: QuranTextForm
    #: Matching-only normalisation (never displayed as the ayah text).
    ayah_text_normalized: NonEmptyStr
    #: Official dump version the text came from (e.g. "2026-10-02").
    dump_version: NonEmptyStr


class _PassageMetadata(BaseModel):
    """Common metadata for a Quranpedia book passage (tafsir / asbab).

    Quranpedia exposes NO passage id. A passage is identified by its official,
    retrievable address (book + surah + ayah -> Evidence.source_address), its
    provider/printed reference, `retrieved_at` and the exact-text fingerprint. The provider's
    own ayah association is preserved faithfully: a passage may be associated with
    one ayah or with several (e.g. al-Wahidi "1,2,3,4,5,6,7").
    """

    model_config = ConfigDict(frozen=True)

    provider_book_id: Annotated[int, Field(ge=1)]
    #: Book title exactly as returned by the provider.
    provider_book_name: NonEmptyStr
    #: Author as returned by the provider. None when the provider supplies none
    #: (e.g. al-Wahidi book 2919). Mizan never fills it in; the approved-source
    #: identity lives in the Trusted Sources Policy (Evidence.trusted_source_id).
    provider_author: str | None = None
    #: The ayah whose official address was requested (surah/ayah of source_address).
    requested_ayah: AyahRef
    surah_name_ar: NonEmptyStr
    #: Every ayah the provider associates with this passage, in provider order.
    associated_ayahs: list[AyahRef] = Field(min_length=1)
    #: The provider's raw association value, verbatim (e.g. "1,2,3,4,5,6,7").
    provider_ayah_association: NonEmptyStr
    #: Volume / page exactly as supplied by the provider (verbatim, may be None).
    provider_part: str | None = None
    provider_page: str | None = None
    #: What `provider_page` means for this book (verified per book from official data):
    #:   printed  — page of the identified printed edition (e.g. Ibn Kathir 136, Dar Taybah);
    #:   provider — the provider's pagination; the printed edition is not identified;
    #:   none     — not a page number (e.g. Muyassar 2012, where it equals the ayah id).
    page_kind: Literal["printed", "provider", "none"]
    #: Position of the passage in the provider response. Display order only —
    #: NOT an identifier.
    position_in_response: Annotated[int, Field(ge=0)]

    @property
    def ayah_range(self) -> tuple[int, int, int] | None:
        """(surah, first, last) ONLY when the association is faithfully a contiguous
        range within one surah; otherwise None (keep the explicit list)."""
        refs = self.associated_ayahs
        if len({r.surah_number for r in refs}) != 1:
            return None
        numbers = [r.ayah_number for r in refs]
        if numbers != list(range(numbers[0], numbers[0] + len(numbers))):
            return None
        return refs[0].surah_number, numbers[0], numbers[-1]


class TafsirMetadata(_PassageMetadata):
    source_type: Literal[SourceType.TAFSIR] = SourceType.TAFSIR


class AsbabNuzulMetadata(_PassageMetadata):
    source_type: Literal[SourceType.ASBAB_NUZUL] = SourceType.ASBAB_NUZUL
    #: Direct sabab vs contextual material. `unspecified` unless the PROVIDER states
    #: it; never inferred by an LLM or heuristic.
    relation_type: AsbabRelationType = AsbabRelationType.UNSPECIFIED


class HadithMetadata(BaseModel):
    """Hadith metadata. Mizan NEVER creates a grading.

    `grading` is copied from the trusted source and must be attributed to the
    relevant `muhaddith`. It may be absent if the source record has none — it
    is never filled in by the system or an LLM.
    """

    model_config = ConfigDict(frozen=True)

    source_type: Literal[SourceType.HADITH] = SourceType.HADITH
    hadith_text: NonEmptyStr
    hadith_text_normalized: NonEmptyStr
    narrator: str | None = None
    muhaddith: str | None = None
    hadith_source: NonEmptyStr
    source_reference: NonEmptyStr
    grading: str | None = None
    grading_details: str | None = None
    dorar_result_id: NonEmptyStr

    @model_validator(mode="after")
    def _grading_is_attributed(self) -> HadithMetadata:
        if self.grading and not (self.muhaddith and self.muhaddith.strip()):
            raise ValueError("a hadith grading must be attributed to a muhaddith")
        return self


EvidenceMetadata = Annotated[
    QuranMetadata | TafsirMetadata | AsbabNuzulMetadata | HadithMetadata,
    Field(discriminator="source_type"),
]


class Evidence(BaseModel):
    """A single traceable evidence record from an approved source."""

    model_config = ConfigDict(frozen=True)

    evidence_id: NonEmptyStr
    source_type: SourceType
    text: NonEmptyStr
    #: Scientific source name (e.g. "تفسير ابن كثير").
    source_name: NonEmptyStr
    provider: Provider
    #: Allowlist key — links this record to the Trusted Sources Policy.
    trusted_source_id: TrustedSourceId
    #: Human-readable reference built ONLY from verified provider metadata.
    reference: NonEmptyStr
    #: Official, retrievable provider address of the original record
    #: (e.g. "/v1/ayah/2/255/book/136"). Required for every evidence item.
    source_address: NonEmptyStr
    #: Full URL of the official address, when the provider has one.
    source_url: HttpUrl | None = None
    #: The provider's OWN record id, only when the provider supplies one
    #: (e.g. Quranpedia ayah id). Never invented.
    source_record_id: str | None = None
    retrieval_channel: RetrievalChannel
    #: Provider data version (required for official dumps).
    source_version: str | None = None
    retrieved_at: datetime
    #: Exact-text fingerprint of `text` (SHA-256 hex).
    text_sha256: NonEmptyStr
    #: Deterministic transformation from the provider's text to `text`.
    text_transform: NonEmptyStr
    metadata: EvidenceMetadata

    @model_validator(mode="after")
    def _trusted_and_consistent(self) -> Evidence:
        try:
            src = get_trusted_source(self.trusted_source_id)
        except KeyError as exc:  # pragma: no cover - enum already restricts
            raise UntrustedSourceError(str(exc)) from exc
        if src.provider != self.provider:
            raise ValueError(
                f"provider {self.provider.value} is not the approved provider for "
                f"{src.id.value} ({src.provider.value})"
            )
        if src.source_type != self.source_type:
            raise ValueError(
                f"source_type {self.source_type.value} does not match approved source "
                f"{src.id.value} ({src.source_type.value})"
            )
        if self.metadata.source_type != self.source_type:
            raise ValueError("metadata type does not match evidence source_type")
        # --- No Evidence Without Traceability ---
        if not _SHA256.match(self.text_sha256) or self.text_sha256 != text_fingerprint(self.text):
            raise ValueError("text_sha256 must be the SHA-256 fingerprint of text")
        if self.source_record_id is not None and not self.source_record_id.strip():
            raise ValueError("source_record_id, when present, must be the provider's own id")
        if self.retrieval_channel == RetrievalChannel.OFFICIAL_DUMP and not self.source_version:
            raise ValueError("evidence from an official dump must state the dump version")
        if (
            isinstance(self.metadata, AsbabNuzulMetadata)
            and self.provider == Provider.QURANPEDIA
            and self.metadata.relation_type != AsbabRelationType.UNSPECIFIED
        ):
            raise ValueError(
                "Quranpedia does not state the asbab relation; relation_type must be unspecified"
            )
        if isinstance(self.metadata, _PassageMetadata):
            bound = src.quranpedia_book_id
            if bound is not None and self.metadata.provider_book_id != bound:
                raise ValueError(
                    f"{src.id.value} is bound to Quranpedia book {bound}, "
                    f"not {self.metadata.provider_book_id}"
                )
        if isinstance(self.metadata, QuranMetadata):
            bound = src.quranpedia_mushaf_id
            if bound is not None and self.metadata.mushaf_id != bound:
                raise ValueError(f"Quran evidence must come from Mushaf {bound}")
        return self
