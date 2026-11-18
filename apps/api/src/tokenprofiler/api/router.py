from __future__ import annotations

from fastapi import APIRouter

from tokenprofiler.api.routes import (
    alerts,
    archives,
    auth,
    health,
    ingest,
    metrics,
    prices,
    projects,
    prompts,
    system,
    traces,
    users,
)

api_router = APIRouter()
for module in (
    health,
    system,
    auth,
    users,
    projects,
    traces,
    metrics,
    prompts,
    prices,
    alerts,
    archives,
    ingest,
):
    api_router.include_router(module.router)
