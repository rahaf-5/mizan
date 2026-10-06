"""Application configuration (environment variables / backend/.env).

Secrets are SecretStr and never logged or returned by the API.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    app_name: str = "Mizan | ميزان"
    app_env: Literal["development", "test", "production"] = "development"
    app_version: str = "0.1.0"
    cors_origins: str = "http://localhost:3000"

    # Database
    database_url: SecretStr | None = None
    database_connect_timeout_seconds: int = Field(default=3, ge=1, le=60)

    # LLM (assistive only; never an evidence source)
    #: Active LLM adapter behind the provider-neutral abstraction (app/llm/base.py).
    llm_provider: Literal["none", "gemini"] = "none"
    llm_request_timeout_seconds: int = Field(default=45, ge=1, le=180)
    # Gemini Developer API (current MVP adapter). Key is backend-only.
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_thinking_level: Literal["", "minimal", "low", "medium", "high"] = "low"

    # Trusted sources. Quranpedia: official public API (no key) + official Mushaf 1 dump.
    quranpedia_enabled: bool = True
    quranpedia_base_url: str | None = None  # default: https://api.quranpedia.net/v1
    #: Where `python -m app.cli.sync_quran_dump` stores the official dump (git-ignored).
    quran_data_dir: str | None = None
    # Dorar: approved but UNAVAILABLE by policy (blocked); this flag cannot override policy.
    quranpedia_api_key: SecretStr | None = None
    dorar_enabled: bool = False
    dorar_base_url: str | None = None
    dorar_api_key: SecretStr | None = None
    source_request_timeout_seconds: int = Field(default=15, ge=1, le=120)

    # Verification pipeline — implementation default, NOT a product rule.
    verification_max_retries: int = Field(default=2, ge=0, le=10)

    @field_validator(
        "database_url",
        "gemini_api_key",
        "quranpedia_api_key",
        "dorar_api_key",
        "quranpedia_base_url",
        "dorar_base_url",
        "quran_data_dir",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, v):  # type: ignore[no-untyped-def]
        return None if isinstance(v, str) and not v.strip() else v

    @property
    def cors_origin_list(self) -> list[str]:
        # A browser Origin has no trailing slash; tolerate one pasted from the address bar.
        return [
            o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip().rstrip("/")
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
