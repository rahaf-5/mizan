"""Database engine/session helpers and a connectivity check."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings


@lru_cache
def _engine_for(url: str, timeout: int) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": timeout},
    )


def get_engine(settings: Settings | None = None) -> Engine | None:
    settings = settings or get_settings()
    if settings.database_url is None:
        return None
    return _engine_for(
        settings.database_url.get_secret_value(), settings.database_connect_timeout_seconds
    )


def get_session(settings: Settings | None = None) -> Session:
    engine = get_engine(settings)
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured")
    return sessionmaker(bind=engine)()


def check_database(settings: Settings | None = None) -> tuple[str, str | None]:
    """Return (status, detail): ok | not_configured | unavailable. Never leaks the URL."""
    engine = get_engine(settings)
    if engine is None:
        return "not_configured", "DATABASE_URL is not set"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok", None
    except Exception as exc:  # noqa: BLE001
        return "unavailable", type(exc).__name__
