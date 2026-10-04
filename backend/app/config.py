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
    llm_provider: Literal["none", "fake", "anthropic"] = "none"
    llm_model: str | None = None
    anthropic_api_key: SecretStr | None = None

    # Trusted sources (placeholders)
    quranpedia_enabled: bool = False
    quranpedia_base_url: str | None = None
    quranpedia_api_key: SecretStr | None = None
    dorar_enabled: bool = False
    dorar_base_url: str | None = None
    dorar_api_key: SecretStr | None = None
    source_request_timeout_seconds: int = Field(default=15, ge=1, le=120)

    # Verification pipeline — implementation default, NOT a product rule.
    verification_max_retries: int = Field(default=2, ge=0, le=10)

    @field_validator(
        "database_url",
        "anthropic_api_key",
        "quranpedia_api_key",
        "dorar_api_key",
        "llm_model",
        "quranpedia_base_url",
        "dorar_base_url",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, v):  # type: ignore[no-untyped-def]
        return None if isinstance(v, str) and not v.strip() else v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
