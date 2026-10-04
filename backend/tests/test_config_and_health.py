from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.llm.factory import build_llm_provider
from app.main import create_app


def client_with(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_defaults_load_without_env():
    s = Settings()
    assert s.verification_max_retries == 2  # implementation default only
    assert s.llm_provider == "none"
    assert s.database_url is None
    assert s.quranpedia_enabled is False and s.dorar_enabled is False


def test_env_overrides_and_blank_values(monkeypatch):
    monkeypatch.setenv("VERIFICATION_MAX_RETRIES", "4")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    s = Settings()
    assert s.verification_max_retries == 4
    assert s.gemini_api_key is None


def test_llm_provider_none_by_default():
    assert build_llm_provider(Settings()) is None
    p = build_llm_provider(Settings(llm_provider="gemini", gemini_api_key="k" * 39))
    assert p is not None and p.name == "gemini" and p.is_configured()


def test_live_endpoint():
    r = client_with(Settings()).get("/api/v1/health/live")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_health_without_database_is_degraded_and_reports_placeholders():
    body = client_with(Settings()).get("/api/v1/health").json()
    assert body["config_loaded"] is True
    assert body["status"] == "degraded"
    assert body["database"]["status"] == "not_configured"
    assert body["trusted_sources"] == {
        "quranpedia": {"status": "disabled", "detail": None},
        "dorar_al_sunniyah": {"status": "disabled", "detail": None},
    }
    assert body["llm_provider"]["status"] == "not_configured"
    assert "ocr" not in body  # image input / OCR is out of MVP scope


def test_health_unreachable_database_and_no_secret_leak():
    secret = "s3cr3t-pass"
    s = Settings(
        database_url=f"postgresql+psycopg://u:{secret}@127.0.0.1:1/db",
        database_connect_timeout_seconds=1,
        gemini_api_key="sk-test-secret",
        llm_provider="gemini",
    )
    r = client_with(s).get("/api/v1/health")
    assert r.json()["database"]["status"] == "unavailable"
    assert secret not in r.text and "sk-test-secret" not in r.text


def test_cors_allows_frontend_origin():
    c = client_with(Settings())
    r = c.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_leftover_ocr_settings_are_ignored_and_never_exposed(monkeypatch):
    """A stale GOOGLE_VISION_API_KEY / OCR_PROVIDER must not affect startup or health."""
    secret = "AIza" + "z" * 35
    monkeypatch.setenv("OCR_PROVIDER", "google_vision")
    monkeypatch.setenv("GOOGLE_VISION_API_KEY", "\u200f" + secret)
    get_settings.cache_clear()
    s = Settings()
    assert not hasattr(s, "google_vision_api_key") and not hasattr(s, "ocr_provider")
    c = client_with(s)
    r = c.get("/api/v1/health")
    assert r.status_code == 200
    assert "ocr" not in r.json() and secret not in r.text and "vision" not in r.text.lower()


def test_no_ocr_endpoint_in_mvp():
    c = client_with(Settings())
    assert c.post("/api/v1/ocr").status_code == 404
    assert c.get("/api/v1/ocr/limits").status_code == 404
    paths = c.get("/openapi.json").json()["paths"]
    assert not [p for p in paths if "ocr" in p]
