"""Trusted-source adapter contract.

An adapter turns a provider's records into validated `Evidence`. It must:
  * serve only allowlisted sources of its own provider;
  * populate reference/citation fields from the provider's verified metadata only;
  * report technical failures as exceptions (SourceUnavailableError, ...), never
    as "no evidence";
  * never fall back to general web search, unapproved sites or LLM knowledge.

Adapters return `SourceHit`s (evidence + why it was looked at). Ranking, merging
and deduplication belong to Hybrid Retrieval, not to adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import RetrievalMatchBasis, RetrievalMethod
from app.domain.evidence import AyahRef, Evidence
from app.domain.trusted_sources import Provider, TrustedSourceId


class AdapterConnectionState(str, Enum):
    NOT_CONNECTED = "not_connected"  # integration details not yet provided / blocked
    DISABLED = "disabled"  # turned off by configuration
    CONFIGURED = "configured"  # configured; live reachability not checked here


class SourceQuery(BaseModel):
    """One request to ONE approved source with ONE retrieval method.

    * `query_text`  — text to search (exact quote or keywords); confirmed_claim_text is never
      modified.
    * `ayah_refs`   — ayahs already validated against the official Quran source.
    * `anchor`      — for ayah-anchored sources (tafsir/asbab): the validated ayah to fetch.
    """

    model_config = ConfigDict(frozen=True)

    source: TrustedSourceId
    method: RetrievalMethod
    query_text: str | None = None
    ayah_refs: list[AyahRef] = Field(default_factory=list)
    anchor: AyahRef | None = None
    #: Basis to record for hits produced from `ayah_refs` / `anchor`.
    basis: RetrievalMatchBasis | None = None
    limit: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def _has_input(self) -> SourceQuery:
        if (
            not (self.query_text and self.query_text.strip())
            and not self.ayah_refs
            and not self.anchor
        ):
            raise ValueError("a source query needs query_text, ayah_refs or an anchor")
        return self


class SourceHit(BaseModel):
    """One record returned by an adapter, before ranking."""

    model_config = ConfigDict(frozen=True)

    evidence: Evidence
    method: RetrievalMethod
    match_basis: RetrievalMatchBasis
    #: Method-specific match score (NOT a truth score).
    score: float | None = None
    anchor_ayah: AyahRef | None = None


class TrustedSourceAdapter(ABC):
    """Base class for provider adapters (Quranpedia, Dorar al-Sunniyah)."""

    provider: Provider
    served_sources: frozenset[TrustedSourceId]

    @property
    @abstractmethod
    def supported_methods(self) -> frozenset[RetrievalMethod]:
        """Retrieval methods this provider genuinely supports (unknown => empty)."""

    @abstractmethod
    def connection_state(self) -> AdapterConnectionState: ...

    @abstractmethod
    async def search(self, query: SourceQuery) -> list[SourceHit]:
        """Search ONE approved source with ONE retrieval method."""

    @abstractmethod
    async def get_records(self, source: TrustedSourceId, source_address: str) -> list[Evidence]:
        """Re-fetch the original record(s) at an official address (traceability)."""
