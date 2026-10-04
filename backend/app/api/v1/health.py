"""Health endpoints: liveness and a configuration/dependency report (no secrets)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.db.session import check_database
from app.ocr.factory import build_ocr_provider
from app.sources.registry import build_default_registry

router = APIRouter(prefix="/health", tags=["health"])


class ComponentStatus(BaseModel):
    status: str
    detail: str | None = None


class HealthReport(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    version: str
    environment: str
    config_loaded: bool
    database: ComponentStatus
    llm_provider: ComponentStatus
    ocr: ComponentStatus
    trusted_sources: dict[str, ComponentStatus]


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("", response_model=HealthReport)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthReport:
    db_status, db_detail = await run_in_threadpool(check_database, settings)
    registry = build_default_registry(settings)
    sources = {
        a.provider.value: ComponentStatus(status=a.connection_state().value)
        for a in registry.adapters()
    }
    return HealthReport(
        # Only the database is required for "ok" at this stage; sources/LLM/OCR
        # are expected to be unconnected during Task 1.
        status="ok" if db_status == "ok" else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        config_loaded=True,
        database=ComponentStatus(status=db_status, detail=db_detail),
        llm_provider=ComponentStatus(
            status="not_configured" if settings.llm_provider == "none" else "configured",
            detail=settings.llm_provider,
        ),
        ocr=_ocr_status(settings),
        trusted_sources=sources,
    )


def _ocr_status(settings: Settings) -> ComponentStatus:
    provider = build_ocr_provider(settings)
    if provider is None:
        return ComponentStatus(status="not_configured", detail="none")
    if provider.is_configured():
        return ComponentStatus(status="configured", detail=provider.name)
    problem = getattr(provider, "config_problem", None) or ""
    status = "missing_credentials" if problem.endswith("is not set") else "invalid_credentials"
    return ComponentStatus(
        status=status, detail=f"{provider.name}: {problem}" if problem else provider.name
    )
