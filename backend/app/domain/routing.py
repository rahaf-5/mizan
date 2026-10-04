"""Source Routing models (spec §5).

- Each claim is routed only to qualified approved sources. No random search.
- Multiple independent claims are split by Claim Extraction first; a routing
  plan has several routes only when ONE logically coherent confirmed claim
  needs different qualified source types (approved).
- Cross-source verification needs an explicit strong logical signal and never
  authorizes open search.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import ClaimType
from app.domain.trusted_sources import TrustedSourceId, get_trusted_source


class SourceRoute(BaseModel):
    model_config = ConfigDict(frozen=True)

    #: The part of the claim this route verifies (None = whole claim).
    component_text: str | None = None
    #: What this route must establish, expressed as the qualified claim type.
    required_claim_type: ClaimType
    sources: list[TrustedSourceId] = Field(min_length=1)
    is_cross_source_check: bool = False
    #: Required when is_cross_source_check is True.
    cross_source_signal: str | None = None

    @model_validator(mode="after")
    def _sources_qualified(self) -> SourceRoute:
        for sid in self.sources:
            if self.required_claim_type not in get_trusted_source(sid).qualified_for:
                raise ValueError(
                    f"source {sid.value} is not qualified to establish "
                    f"{self.required_claim_type.value} (Source Boundary)"
                )
        if self.is_cross_source_check and not (
            self.cross_source_signal and self.cross_source_signal.strip()
        ):
            raise ValueError("cross-source verification requires a stated logical signal")
        return self


class SourceRoutingPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_id: str
    routes: list[SourceRoute] = Field(min_length=1)

    @property
    def is_composite(self) -> bool:
        """True when one coherent claim needs more than one qualified source type."""
        return len({r.required_claim_type for r in self.routes}) > 1

    @property
    def all_sources(self) -> list[TrustedSourceId]:
        seen: list[TrustedSourceId] = []
        for r in self.routes:
            for s in r.sources:
                if s not in seen:
                    seen.append(s)
        return seen
