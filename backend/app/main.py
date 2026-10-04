"""Mizan FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import get_settings
from app.core_logging import configure_logging, get_logger


def _warn_on_ocr_misconfiguration(settings) -> None:  # type: ignore[no-untyped-def]
    """Surface OCR credential problems at startup (never logs the key itself)."""
    from app.ocr.factory import build_ocr_provider

    provider = build_ocr_provider(settings)
    problem = getattr(provider, "config_problem", None) if provider else None
    if problem:
        get_logger("startup").warning("OCR provider '%s' not usable: %s", provider.name, problem)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    _warn_on_ocr_misconfiguration(settings)
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()
