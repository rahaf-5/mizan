"""POST /api/v1/verify (backend only)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.v1.claims import get_llm_provider
from app.api.v1.verify import get_registry
from app.config import Settings, get_settings
from app.domain.enums import ClaimType
from app.main import create_app
from tests.test_task5a_pipeline import registry
from tests.test_verification_engine import ScriptedLLM, cls, handler


def client(llm, settings=None):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings or Settings()
    app.dependency_overrides[get_llm_provider] = lambda: llm
    app.dependency_overrides[get_registry] = lambda: registry(handler=handler)
    return TestClient(app)


def claim(
    cid="c1",
    text="قال تعالى في سورة آل عمران: «إن الصفا والمروة من شعائر الله»",
    status="confirmed",
):
    return {"claim_id": cid, "confirmed_claim_text": text, "user_confirmation_status": status}


def test_verify_returns_validated_outcomes():
    r = client(ScriptedLLM(cls(ClaimType.QURAN))).post("/api/v1/verify", json={"claims": [claim()]})
    assert r.status_code == 200
    [o] = r.json()["outcomes"]
    assert o["kind"] == "verification" and o["status"] == "contradicted"
    loc = next(c for c in o["analysis"]["components"] if c["kind"] == "quran_location")
    assert loc["outcome"] == "contradicted" and loc["verified_location"][0]["ayah_number"] == 158
    assert all(e["source_address"] and e["text_sha256"] for e in o["evidence"])
    assert o["result_group"] is None and o["why"] is None  # presentation is Task 7


def test_hadith_claim_returns_required_source_unavailable():
    r = client(ScriptedLLM(cls(ClaimType.HADITH))).post(
        "/api/v1/verify", json={"claims": [claim(text="قال رسول الله ﷺ: «إنما الأعمال بالنيات»")]}
    )
    [o] = r.json()["outcomes"]
    assert o["kind"] == "required_source_unavailable" and "status" not in o


def test_only_confirmed_claims_are_accepted():
    r = client(ScriptedLLM(cls(ClaimType.QURAN))).post(
        "/api/v1/verify", json={"claims": [claim(status="pending")]}
    )
    assert r.status_code == 422


def test_duplicate_ids_and_missing_llm():
    c = client(ScriptedLLM(cls(ClaimType.QURAN)))
    assert c.post("/api/v1/verify", json={"claims": [claim(), claim()]}).status_code == 422
    r = client(None).post("/api/v1/verify", json={"claims": [claim()]})
    assert r.status_code == 503 and r.json()["error"]["code"] == "llm_not_configured"


def test_system_error_messages_are_generic():
    import httpx

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(verification_max_retries=0)
    app.dependency_overrides[get_llm_provider] = lambda: ScriptedLLM(cls(ClaimType.TAFSIR))
    app.dependency_overrides[get_registry] = lambda: registry(handler=lambda r: httpx.Response(503))
    r = TestClient(app).post(
        "/api/v1/verify",
        json={"claims": [claim(text="معنى «لا تأخذه سنة ولا نوم» أن الله لا يأخذه نعاس")]},
    )
    [o] = r.json()["outcomes"]
    assert o["kind"] == "system_error" and o["error"]["code"] == "verification_incomplete"
    assert (
        "quranpedia" not in o["error"]["message"].lower() and "/ayah/" not in o["error"]["message"]
    )
