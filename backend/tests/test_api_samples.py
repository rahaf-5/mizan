"""Real API response samples for the frontend contract test.

Every sample is produced by the actual FastAPI app (`/api/v1/verify`,
`/api/v1/alternative-wording`) with a scripted LLM and recorded provider responses. The
frontend test `tests/unit/api-samples.test.ts` checks that every field the UI reads exists in
these real responses. Regenerate after an intentional response change:

    MIZAN_UPDATE_API_SAMPLES=1 pytest tests/test_api_samples.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.api.v1.claims import get_llm_provider
from app.api.v1.verify import get_registry
from app.config import Settings, get_settings
from app.domain.enums import ClaimType
from app.llm.schemas import AnalysisRelation
from app.main import create_app
from tests.test_results_and_alternatives import WRONG_SURAH, AltLLM
from tests.test_task5a_pipeline import registry
from tests.test_verification_engine import TAFSIR_CLAIM, ScriptedLLM, analysis_for, cls, handler

SAMPLES_PATH = Path(__file__).resolve().parents[2] / "contracts" / "api-samples.json"


def _client(llm, reg_handler=handler, retries=2) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(verification_max_retries=retries)
    app.dependency_overrides[get_llm_provider] = lambda: llm
    app.dependency_overrides[get_registry] = lambda: registry(handler=reg_handler)
    return TestClient(app)


def _verify(c: TestClient, text: str) -> dict:
    r = c.post(
        "/api/v1/verify",
        json={
            "claims": [
                {
                    "claim_id": "c1",
                    "confirmed_claim_text": text,
                    "user_confirmation_status": "confirmed",
                }
            ]
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def _tafsir_gap(r: httpx.Request) -> httpx.Response:
    if r.url.path.endswith("/book/136"):
        return httpx.Response(200, json={"book": {"id": 136, "name": "ك"}, "content": []})
    return handler(r)


def build_samples() -> dict:
    def tafsir_judge(label, source):
        if "الميسر" in source:
            return AnalysisRelation.SUPPORTS, "لا تأخذه سنة أي: نعاس"
        return AnalysisRelation.CONTRADICTS, "لا يغلبه نعاس ولا نوم"

    def supports_only(label, source):
        return AnalysisRelation.SUPPORTS, "لا تأخذه سنة أي: نعاس"

    alt_llm = AltLLM("قال تعالى في سورة البقرة: «إن الصفا والمروة من شعائر الله»")
    alt_client = _client(alt_llm)
    contradicted = _verify(alt_client, WRONG_SURAH)
    alternative = alt_client.post(
        "/api/v1/alternative-wording",
        json={"run_id": contradicted["run_id"], "claim_id": "c1"},
    ).json()
    return {
        "verify_contradicted_quran": contradicted,
        "verify_conflicting_tafsir": _verify(
            _client(ScriptedLLM(cls(ClaimType.TAFSIR), analysis_for(tafsir_judge))),
            TAFSIR_CLAIM,
        ),
        "verify_supported_tafsir_with_limitation": _verify(
            _client(
                ScriptedLLM(cls(ClaimType.TAFSIR), analysis_for(supports_only)),
                reg_handler=_tafsir_gap,
            ),
            TAFSIR_CLAIM,
        ),
        "verify_hadith_unavailable": _verify(
            _client(ScriptedLLM(cls(ClaimType.HADITH))), "قال رسول الله ﷺ: «إنما الأعمال بالنيات»"
        ),
        "verify_out_of_scope": _verify(_client(ScriptedLLM(cls(None))), "صيام يوم الاثنين واجب"),
        "verify_system_error": _verify(
            _client(
                ScriptedLLM(cls(ClaimType.TAFSIR)),
                reg_handler=lambda r: httpx.Response(503),
                retries=0,
            ),
            TAFSIR_CLAIM,
        ),
        "alternative_verified": alternative,
    }


def shape(value, prefix: str = "") -> set[str]:
    """Key paths of a JSON value (array items merged) — values are ignored."""
    out: set[str] = set()
    if isinstance(value, dict):
        for k, v in value.items():
            path = f"{prefix}.{k}" if prefix else k
            out.add(path)
            out |= shape(v, path)
    elif isinstance(value, list):
        for item in value:
            out |= shape(item, f"{prefix}[]")
    return out


def test_api_samples_snapshot_is_current():
    samples = build_samples()
    kinds = {name: [o["kind"] for o in s.get("outcomes", [])] for name, s in samples.items()}
    assert kinds["verify_contradicted_quran"] == ["verification"]
    assert kinds["verify_hadith_unavailable"] == ["required_source_unavailable"]
    assert kinds["verify_out_of_scope"] == ["out_of_scope"]
    assert kinds["verify_system_error"] == ["system_error"]
    conflict = samples["verify_conflicting_tafsir"]["outcomes"][0]
    assert (
        conflict["status"] == "conflicting_evidence" and conflict["analysis"]["evidence_conflicts"]
    )
    limited = samples["verify_supported_tafsir_with_limitation"]
    assert limited["outcomes"][0]["status"] == "supported"
    assert limited["outcomes"][0]["limitations"] and limited["limitations"]
    assert samples["alternative_verified"]["verified"] is True
    assert samples["verify_contradicted_quran"]["outcomes"][0]["verified_reference"]

    if os.environ.get("MIZAN_UPDATE_API_SAMPLES") == "1":
        SAMPLES_PATH.write_text(
            json.dumps(samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    committed = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    for name, sample in samples.items():
        assert shape(sample) == shape(committed[name]), (
            f"{name}: API response shape changed — regenerate with MIZAN_UPDATE_API_SAMPLES=1"
        )
