"""Trusted Sources Policy — MVP Allowlist (spec §5).

This is product policy, so it lives in the domain layer. Adapters
(app/sources) can only serve sources listed here. Adding a source requires
explicit product approval and a change to the contract snapshot.
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from app.domain.enums import ClaimType, SourceAvailability, SourceType


class Provider(str, Enum):
    QURANPEDIA = "quranpedia"
    DORAR_AL_SUNNIYAH = "dorar_al_sunniyah"


class TrustedSourceId(str, Enum):
    QURAN = "quran"
    TAFSIR_AL_MUYASSAR = "tafsir_al_muyassar"
    TAFSIR_IBN_KATHIR = "tafsir_ibn_kathir"
    ASBAB_AL_NUZUL_AL_WAHIDI = "asbab_al_nuzul_al_wahidi"
    AL_MUHARRAR_FI_ASBAB_AL_NUZUL = "al_muharrar_fi_asbab_al_nuzul"
    DORAR_HADITH = "dorar_hadith"


class TrustedSource(BaseModel):
    """One approved source and what it is qualified to establish (Source Boundary)."""

    model_config = ConfigDict(frozen=True)

    id: TrustedSourceId
    name_ar: str
    name_en: str
    provider: Provider
    source_type: SourceType
    #: Claim types this source is qualified to establish evidence for.
    qualified_for: frozenset[ClaimType]
    #: Human-readable statement of the source boundary (spec §5 Source Routing).
    establishes: str
    #: Product-level availability. An UNAVAILABLE source stays approved, but claims
    #: that require it end as `required_source_unavailable` (never a status).
    availability: SourceAvailability = SourceAvailability.AVAILABLE
    availability_note: str | None = None
    #: Exact provider binding, verified through the official Quranpedia API
    #: (docs/SOURCE_VALIDATION.md). Locked 2026-10-04.
    quranpedia_mushaf_id: int | None = None
    quranpedia_book_id: int | None = None

    @property
    def is_available(self) -> bool:
        return self.availability == SourceAvailability.AVAILABLE


_ALLOWLIST: tuple[TrustedSource, ...] = (
    TrustedSource(
        id=TrustedSourceId.QURAN,
        name_ar="القرآن الكريم",
        name_en="The Quran",
        provider=Provider.QURANPEDIA,
        source_type=SourceType.QURAN,
        qualified_for=frozenset({ClaimType.QURAN}),
        establishes="ayah existence, text and reference",
        quranpedia_mushaf_id=1,
    ),
    TrustedSource(
        id=TrustedSourceId.TAFSIR_AL_MUYASSAR,
        name_ar="التفسير الميسر",
        name_en="Tafsir al-Muyassar",
        provider=Provider.QURANPEDIA,
        source_type=SourceType.TAFSIR,
        qualified_for=frozenset({ClaimType.TAFSIR}),
        establishes="meaning / tafsir",
        # 2012 covers all 6,236 ayahs (official dump). Book 32 has richer printed-edition
        # metadata but covers only 5,042 ayahs — documented, not used for retrieval.
        quranpedia_book_id=2012,
    ),
    TrustedSource(
        id=TrustedSourceId.TAFSIR_IBN_KATHIR,
        name_ar="تفسير ابن كثير",
        name_en="Tafsir Ibn Kathir",
        provider=Provider.QURANPEDIA,
        source_type=SourceType.TAFSIR,
        qualified_for=frozenset({ClaimType.TAFSIR}),
        establishes="meaning / tafsir",
        quranpedia_book_id=136,
    ),
    TrustedSource(
        id=TrustedSourceId.ASBAB_AL_NUZUL_AL_WAHIDI,
        name_ar="أسباب النزول للواحدي",
        name_en="Asbab al-Nuzul by al-Wahidi",
        provider=Provider.QURANPEDIA,
        source_type=SourceType.ASBAB_NUZUL,
        qualified_for=frozenset({ClaimType.ASBAB_NUZUL}),
        establishes="sabab al-nuzul",
        quranpedia_book_id=2919,
    ),
    TrustedSource(
        id=TrustedSourceId.AL_MUHARRAR_FI_ASBAB_AL_NUZUL,
        name_ar="المحرر في أسباب النزول",
        name_en="Al-Muharrar fi Asbab al-Nuzul",
        provider=Provider.QURANPEDIA,
        source_type=SourceType.ASBAB_NUZUL,
        qualified_for=frozenset({ClaimType.ASBAB_NUZUL}),
        establishes="sabab al-nuzul",
        quranpedia_book_id=460,
    ),
    TrustedSource(
        id=TrustedSourceId.DORAR_HADITH,
        name_ar="الدرر السنية — الموسوعة الحديثية",
        name_en="Dorar al-Sunniyah — Hadith data and muhaddith rulings",
        provider=Provider.DORAR_AL_SUNNIYAH,
        source_type=SourceType.HADITH,
        qualified_for=frozenset({ClaimType.HADITH}),
        establishes="hadith text, attribution and muhaddith gradings",
        availability=SourceAvailability.UNAVAILABLE,
        availability_note=(
            "Blocked: the official Dorar API returns no per-hadith record id/URL and "
            "storage/caching terms are unresolved (docs/SOURCE_VALIDATION.md)."
        ),
    ),
)

#: Read-only allowlist keyed by source id.
TRUSTED_SOURCES: MappingProxyType[TrustedSourceId, TrustedSource] = MappingProxyType(
    {s.id: s for s in _ALLOWLIST}
)


def get_trusted_source(source_id: TrustedSourceId) -> TrustedSource:
    """Return an approved source. Raises KeyError for anything not on the allowlist."""
    return TRUSTED_SOURCES[TrustedSourceId(source_id)]


def sources_qualified_for(claim_type: ClaimType) -> tuple[TrustedSource, ...]:
    """Approved sources qualified to establish evidence for a claim type."""
    return tuple(s for s in _ALLOWLIST if claim_type in s.qualified_for)


def is_qualified(source_id: TrustedSourceId, claim_type: ClaimType) -> bool:
    return claim_type in get_trusted_source(source_id).qualified_for
