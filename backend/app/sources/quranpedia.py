"""Quranpedia adapter — PLACEHOLDER (Task 5).

Serves (allowlist): Quran, Tafsir al-Muyassar, Tafsir Ibn Kathir,
Asbab al-Nuzul (al-Wahidi), Al-Muharrar fi Asbab al-Nuzul.

No endpoints, request/response schemas, authentication scheme or rate limits
are assumed. All of these must come from official Quranpedia documentation /
agreement. See docs/INTEGRATION_TODO.md.
"""

from __future__ import annotations

from app.domain.enums import PipelineStage, RetrievalMethod
from app.domain.errors import SourceNotConnectedError
from app.domain.evidence import Evidence
from app.domain.retrieval import CandidateEvidence
from app.domain.trusted_sources import Provider, TrustedSourceId
from app.sources.base import AdapterConnectionState, SourceQuery, TrustedSourceAdapter

_NOT_CONNECTED = (
    "Quranpedia integration is not connected yet (pending official API details; Task 5)"
)


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

    def __init__(self, *, enabled: bool = False, base_url: str | None = None) -> None:
        self._enabled = enabled
        self._base_url = base_url or None

    @property
    def supported_methods(self) -> frozenset[RetrievalMethod]:
        return frozenset()  # unknown until API documentation is available

    def connection_state(self) -> AdapterConnectionState:
        if not self._enabled:
            return AdapterConnectionState.DISABLED
        return AdapterConnectionState.NOT_CONNECTED

    async def search(self, query: SourceQuery) -> list[CandidateEvidence]:
        raise SourceNotConnectedError(_NOT_CONNECTED, stage=PipelineStage.HYBRID_RETRIEVAL)

    async def get_record(self, source: TrustedSourceId, source_record_id: str) -> Evidence:
        raise SourceNotConnectedError(_NOT_CONNECTED, stage=PipelineStage.HYBRID_RETRIEVAL)
