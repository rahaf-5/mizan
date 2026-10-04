"""Trusted-source adapter contract.

An adapter turns a provider's records into validated `Evidence` /
`CandidateEvidence`. It must:
  * serve only allowlisted sources of its own provider;
  * populate reference/citation fields from the provider's verified metadata only;
  * report technical failures as exceptions (SourceUnavailableError, ...), never
    as "no evidence";
  * never fall back to general web search, unapproved sites or LLM knowledge.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import RetrievalMethod
from app.domain.evidence import Evidence
from app.domain.retrieval import CandidateEvidence
from app.domain.trusted_sources import Provider, TrustedSourceId


class AdapterConnectionState(str, Enum):
    NOT_CONNECTED = "not_connected"  # integration details not yet provided
    DISABLED = "disabled"  # turned off by configuration
    CONFIGURED = "configured"  # configured; live reachability not checked here


class SourceQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: TrustedSourceId
    method: RetrievalMethod
    #: Query text (may be a reformulation; confirmed_claim_text is never modified).
    query_text: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=100)


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
    async def search(self, query: SourceQuery) -> list[CandidateEvidence]:
        """Search ONE approved source with ONE retrieval method."""

    @abstractmethod
    async def get_record(self, source: TrustedSourceId, source_record_id: str) -> Evidence:
        """Fetch one original record by its provider id (traceability / metadata retry)."""
