from __future__ import annotations

import pytest

from app.config import Settings
from app.domain.enums import RetrievalMethod
from app.domain.errors import SourceNotConnectedError, UntrustedSourceError
from app.domain.trusted_sources import TRUSTED_SOURCES, Provider, TrustedSourceId
from app.sources.base import AdapterConnectionState, SourceQuery
from app.sources.dorar import DorarAdapter
from app.sources.quranpedia import QuranpediaAdapter
from app.sources.registry import AdapterRegistry, build_default_registry


def test_default_registry_covers_exactly_the_allowlist():
    reg = build_default_registry(Settings())
    for sid in TRUSTED_SOURCES:
        assert reg.adapter_for(sid).provider == TRUSTED_SOURCES[sid].provider
    assert len(reg.adapters()) == 2


def test_registry_rejects_wrong_provider():
    class Rogue(DorarAdapter):
        served_sources = frozenset({TrustedSourceId.QURAN})

    with pytest.raises(UntrustedSourceError):
        AdapterRegistry().register(Rogue())


def test_registry_rejects_duplicate_registration():
    reg = AdapterRegistry()
    reg.register(DorarAdapter())
    with pytest.raises(ValueError):
        reg.register(DorarAdapter())


@pytest.mark.parametrize(
    "adapter_cls,source",
    [
        (QuranpediaAdapter, TrustedSourceId.QURAN),
        (DorarAdapter, TrustedSourceId.DORAR_HADITH),
    ],
)
async def test_placeholders_raise_not_connected(adapter_cls, source):
    adapter = adapter_cls(enabled=True)
    assert adapter.connection_state() == AdapterConnectionState.NOT_CONNECTED
    assert adapter.supported_methods == frozenset()  # nothing assumed about provider APIs
    with pytest.raises(SourceNotConnectedError):
        await adapter.search(
            SourceQuery(source=source, method=RetrievalMethod.EXACT, query_text="q")
        )
    with pytest.raises(SourceNotConnectedError):
        await adapter.get_record(source, "id")


def test_disabled_by_default():
    assert QuranpediaAdapter().connection_state() == AdapterConnectionState.DISABLED
    assert DorarAdapter().provider == Provider.DORAR_AL_SUNNIYAH
