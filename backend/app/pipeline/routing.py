"""Deterministic Source Routing (Task 5a).

Each required claim type is routed ONLY to approved sources qualified for it (Source
Boundary). A source is usable only if the Trusted Sources Policy marks it AVAILABLE and its
adapter is configured. If any claim type the claim REQUIRES has no usable source, the whole
claim ends as `RequiredSourceUnavailableOutcome` — an explicit abstention, never a status,
never Out of Scope, never contradiction. No unavailable source is ever called.
"""

from __future__ import annotations

from app.domain.claim import ClassifiedClaim
from app.domain.results import RequiredSourceUnavailableOutcome
from app.domain.routing import SourceRoute, SourceRoutingPlan
from app.domain.trusted_sources import TrustedSourceId, get_trusted_source, sources_qualified_for
from app.sources.base import AdapterConnectionState
from app.sources.registry import AdapterRegistry


class DeterministicSourceRouter:
    def __init__(self, registry: AdapterRegistry) -> None:
        self._registry = registry

    def is_usable(self, source: TrustedSourceId) -> bool:
        if not get_trusted_source(source).is_available:
            return False
        try:
            adapter = self._registry.adapter_for(source)
        except ValueError:  # UntrustedSourceError: no adapter registered
            return False
        return adapter.connection_state() == AdapterConnectionState.CONFIGURED

    async def route(
        self, claim: ClassifiedClaim
    ) -> SourceRoutingPlan | RequiredSourceUnavailableOutcome:
        routes: list[SourceRoute] = []
        unavailable: list[TrustedSourceId] = []
        for claim_type in claim.required_claim_types:
            qualified = [s.id for s in sources_qualified_for(claim_type)]
            usable = [sid for sid in qualified if self.is_usable(sid)]
            if not usable:
                unavailable.extend(sid for sid in qualified if sid not in unavailable)
                continue
            routes.append(SourceRoute(required_claim_type=claim_type, sources=usable))
        if unavailable:
            return RequiredSourceUnavailableOutcome(
                claim_id=claim.claim_id,
                confirmed_claim_text=claim.confirmed_claim_text,
                required_claim_types=claim.required_claim_types,
                unavailable_sources=unavailable,
                detail=(
                    "يتطلب هذا الادعاء مصدرًا معتمدًا غير متاح حاليًا في ميزان؛ لذلك لم يُصدر "
                    "ميزان حكمًا عليه. غياب الدليل هنا لا يعني أن الادعاء غير صحيح."
                ),
            )
        return SourceRoutingPlan(claim_id=claim.claim_id, routes=routes)
