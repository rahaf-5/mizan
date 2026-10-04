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


async def test_dorar_is_blocked_and_never_serves_evidence():
    adapter = DorarAdapter(enabled=True)
    assert adapter.supported_methods == frozenset()  # nothing assumed about provider APIs
    assert not TRUSTED_SOURCES[TrustedSourceId.DORAR_HADITH].is_available
    with pytest.raises(SourceNotConnectedError):
        await adapter.search(
            SourceQuery(
                source=TrustedSourceId.DORAR_HADITH, method=RetrievalMethod.EXACT, query_text="q"
            )
        )
    with pytest.raises(SourceNotConnectedError):
        await adapter.get_records(TrustedSourceId.DORAR_HADITH, "x")


def test_defaults():
    assert QuranpediaAdapter().connection_state() == AdapterConnectionState.CONFIGURED
    assert QuranpediaAdapter(enabled=False).connection_state() == AdapterConnectionState.DISABLED
    assert DorarAdapter().provider == Provider.DORAR_AL_SUNNIYAH


def test_policy_bindings_locked():
    b = {s.id: (s.quranpedia_mushaf_id, s.quranpedia_book_id) for s in TRUSTED_SOURCES.values()}
    assert b[TrustedSourceId.QURAN] == (1, None)
    assert b[TrustedSourceId.TAFSIR_AL_MUYASSAR] == (None, 2012)  # full coverage (not 32)
    assert b[TrustedSourceId.TAFSIR_IBN_KATHIR] == (None, 136)
    assert b[TrustedSourceId.ASBAB_AL_NUZUL_AL_WAHIDI] == (None, 2919)
    assert b[TrustedSourceId.AL_MUHARRAR_FI_ASBAB_AL_NUZUL] == (None, 460)
    assert [s.id for s in TRUSTED_SOURCES.values() if not s.is_available] == [
        TrustedSourceId.DORAR_HADITH
    ]
