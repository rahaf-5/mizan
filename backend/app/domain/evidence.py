"""Unified Evidence Data Schema (spec §4).

Every Evidence record must be traceable:
Evidence -> Scientific Source -> Provider -> Original Record/Chunk -> Reference/Source URL.
Evidence may only come from the Trusted Sources Allowlist, and its metadata must
match its source_type. Evidence records are produced by trusted-source adapters
from verified source metadata — never by an LLM.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.domain.enums import AsbabRelationType, SourceType
from app.domain.errors import UntrustedSourceError
from app.domain.trusted_sources import Provider, TrustedSourceId, get_trusted_source

NonEmptyStr = Annotated[str, Field(min_length=1)]
SurahNumber = Annotated[int, Field(ge=1, le=114)]
AyahNumber = Annotated[int, Field(ge=1)]


class _AyahRangeMixin(BaseModel):
    ayah_start: AyahNumber
    ayah_end: AyahNumber

    @model_validator(mode="after")
    def _range_ok(self):  # type: ignore[no-untyped-def]
        if self.ayah_end < self.ayah_start:
            raise ValueError("ayah_end must be >= ayah_start")
        return self


class QuranMetadata(BaseModel):
    """Uthmani text for display/citation; normalized text for retrieval/matching."""

    model_config = ConfigDict(frozen=True)

    source_type: Literal[SourceType.QURAN] = SourceType.QURAN
    surah_number: SurahNumber
    surah_name_ar: NonEmptyStr
    ayah_number: AyahNumber
    ayah_text_uthmani: NonEmptyStr
    ayah_text_normalized: NonEmptyStr


class TafsirMetadata(_AyahRangeMixin):
    model_config = ConfigDict(frozen=True)

    source_type: Literal[SourceType.TAFSIR] = SourceType.TAFSIR
    tafsir_name: NonEmptyStr
    author: NonEmptyStr
    surah_number: SurahNumber
    surah_name_ar: NonEmptyStr
    chunk_id: NonEmptyStr


class AsbabNuzulMetadata(_AyahRangeMixin):
    model_config = ConfigDict(frozen=True)

    source_type: Literal[SourceType.ASBAB_NUZUL] = SourceType.ASBAB_NUZUL
    asbab_source_name: NonEmptyStr
    author: NonEmptyStr
    surah_number: SurahNumber
    surah_name_ar: NonEmptyStr
    chunk_id: NonEmptyStr
    #: Direct sabab al-nuzul vs contextual material.
    relation_type: AsbabRelationType


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
    #: Reference/location from verified source metadata (never LLM memory).
    reference: NonEmptyStr
    source_url: HttpUrl | None = None
    #: Original record/chunk id at the provider.
    source_record_id: NonEmptyStr
    retrieved_at: datetime
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
        return self
