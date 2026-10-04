"""Adapter registry — enforces the Trusted Sources Allowlist at registration time."""

from __future__ import annotations

from app.domain.errors import UntrustedSourceError
from app.domain.trusted_sources import TRUSTED_SOURCES, TrustedSourceId
from app.sources.base import TrustedSourceAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._by_source: dict[TrustedSourceId, TrustedSourceAdapter] = {}

    def register(self, adapter: TrustedSourceAdapter) -> None:
        for sid in adapter.served_sources:
            src = TRUSTED_SOURCES.get(sid)
            if src is None:
                raise UntrustedSourceError(f"{sid} is not on the Trusted Sources Allowlist")
            if src.provider != adapter.provider:
                raise UntrustedSourceError(
                    f"{sid.value} is approved only via {src.provider.value}, "
                    f"not {adapter.provider.value}"
                )
            if sid in self._by_source:
                raise ValueError(f"an adapter is already registered for {sid.value}")
        for sid in adapter.served_sources:
            self._by_source[sid] = adapter

    def adapter_for(self, source: TrustedSourceId) -> TrustedSourceAdapter:
        try:
            return self._by_source[source]
        except KeyError as exc:
            raise UntrustedSourceError(f"no adapter registered for {source}") from exc

    def adapters(self) -> list[TrustedSourceAdapter]:
        unique: list[TrustedSourceAdapter] = []
        for a in self._by_source.values():
            if a not in unique:
                unique.append(a)
        return unique


def build_default_registry(settings) -> AdapterRegistry:  # type: ignore[no-untyped-def]
    from app.sources.dorar import DorarAdapter
    from app.sources.quranpedia import QuranpediaAdapter

    reg = AdapterRegistry()
    reg.register(
        QuranpediaAdapter(
            enabled=settings.quranpedia_enabled, base_url=settings.quranpedia_base_url
        )
    )
    reg.register(DorarAdapter(enabled=settings.dorar_enabled, base_url=settings.dorar_base_url))
    return reg
