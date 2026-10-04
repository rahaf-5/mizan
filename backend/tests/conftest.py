from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.config import get_settings
from app.domain.enums import RetrievalMethod, SourceType
from app.domain.evidence import Evidence, HadithMetadata, QuranMetadata
from app.domain.retrieval import CandidateEvidence, RetrievalMetadata
from app.domain.trusted_sources import Provider, TrustedSourceId

# Synthetic test fixtures only — NOT real source data and NOT real references.


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch):
    """Tests never read the developer's backend/.env."""
    for var in (
        "DATABASE_URL",
        "LLM_PROVIDER",
        "VERIFICATION_MAX_RETRIES",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "GEMINI_THINKING_LEVEL",
    ):
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
    from app.config import Settings

    monkeypatch.setattr(Settings, "model_config", {**Settings.model_config, "env_file": None})
    yield
    get_settings.cache_clear()


def make_quran_evidence(evidence_id: str = "ev-q-1", **overrides) -> Evidence:
    data = dict(
        evidence_id=evidence_id,
        source_type=SourceType.QURAN,
        text="نص تجريبي",
        source_name="القرآن الكريم",
        provider=Provider.QURANPEDIA,
        trusted_source_id=TrustedSourceId.QURAN,
        reference="test-ref",
        source_record_id="test-record-1",
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        metadata=QuranMetadata(
            surah_number=1,
            surah_name_ar="سورة تجريبية",
            ayah_number=1,
            ayah_text_uthmani="نص تجريبي",
            ayah_text_normalized="نص تجريبي",
        ),
    )
    data.update(overrides)
    return Evidence(**data)


def make_hadith_metadata(**overrides) -> HadithMetadata:
    data = dict(
        hadith_text="نص تجريبي",
        hadith_text_normalized="نص تجريبي",
        hadith_source="مصدر تجريبي",
        source_reference="test-ref",
        dorar_result_id="test-id",
    )
    data.update(overrides)
    return HadithMetadata(**data)


def make_candidate(evidence: Evidence | None = None, rank: int = 1) -> CandidateEvidence:
    ev = evidence or make_quran_evidence()
    return CandidateEvidence(
        evidence=ev,
        retrieval=RetrievalMetadata(
            retrieval_method=RetrievalMethod.EXACT,
            retrieval_rank=rank,
            searched_source=ev.trusted_source_id,
        ),
    )
