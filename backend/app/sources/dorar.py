"""Dorar al-Sunniyah adapter — NOT CONNECTED (product decision).

Serves (allowlist): hadith data and muhaddith rulings.

STATUS (2026-10-04): BLOCKED / UNAVAILABLE by product decision. The official
Dorar API returns no per-hadith record id or URL and storage/caching terms are
unresolved (docs/SOURCE_VALIDATION.md). The Trusted Sources Policy marks
`dorar_hadith` as UNAVAILABLE, so routing never calls this adapter; claims that
require Hadith end as `required_source_unavailable`. Enabling Dorar later means
implementing this adapter and flipping the policy availability — no pipeline
redesign.
Gradings must be copied from Dorar records and attributed to the muhaddith;
Mizan never creates or chooses a grading.

No endpoints, request/response schemas, authentication or usage terms are
assumed. See docs/INTEGRATION_TODO.md.
"""

from __future__ import annotations

from app.domain.enums import PipelineStage, RetrievalMethod
from app.domain.errors import SourceNotConnectedError
from app.domain.evidence import Evidence
from app.domain.trusted_sources import Provider, TrustedSourceId
from app.sources.base import AdapterConnectionState, SourceHit, SourceQuery, TrustedSourceAdapter

_NOT_CONNECTED = "Dorar al-Sunniyah integration is not connected (required source unavailable)"


class DorarAdapter(TrustedSourceAdapter):
    provider = Provider.DORAR_AL_SUNNIYAH
    served_sources = frozenset({TrustedSourceId.DORAR_HADITH})

    def __init__(self, *, enabled: bool = False, base_url: str | None = None) -> None:
        self._enabled = enabled
        self._base_url = base_url or None

    @property
    def supported_methods(self) -> frozenset[RetrievalMethod]:
        return frozenset()

    def connection_state(self) -> AdapterConnectionState:
        if not self._enabled:
            return AdapterConnectionState.DISABLED
        return AdapterConnectionState.NOT_CONNECTED

    async def search(self, query: SourceQuery) -> list[SourceHit]:
        raise SourceNotConnectedError(_NOT_CONNECTED, stage=PipelineStage.HYBRID_RETRIEVAL)

    async def get_records(self, source: TrustedSourceId, source_address: str) -> list[Evidence]:
        raise SourceNotConnectedError(_NOT_CONNECTED, stage=PipelineStage.HYBRID_RETRIEVAL)
