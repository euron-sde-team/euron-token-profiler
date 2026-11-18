"""Dashboard aggregates: the overview and the breakdowns by model, agent, tool and prompt."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from tokenprofiler.api.deps import ContainerDep, ProjectDep, SessionDep
from tokenprofiler.schemas.metrics import Breakdown, Overview
from tokenprofiler.services.dashboards import DashboardService

router = APIRouter(prefix="/api/v1/projects/{project_id}/metrics", tags=["metrics"])


@router.get("/overview", summary="KPIs against the previous period, and the time series")
async def overview(
    project: ProjectDep,
    container: ContainerDep,
    session: SessionDep,
    range: Annotated[str | None, Query(description="1h, 6h, 24h, 7d, 14d or 30d")] = "24h",
    start: datetime | None = None,
    end: datetime | None = None,
    environment: Annotated[str | None, Query(max_length=48)] = None,
) -> Overview:
    return await DashboardService(container, session).overview(
        project.id, range, start, end, environment
    )


@router.get(
    "/breakdown", summary="Cost, tokens, latency and errors per model, agent, tool or prompt"
)
async def breakdown(
    project: ProjectDep,
    container: ContainerDep,
    session: SessionDep,
    dimension: Literal["model", "agent", "tool", "prompt"] = "model",
    range: Annotated[str | None, Query(description="1h, 6h, 24h, 7d, 14d or 30d")] = "7d",
    start: datetime | None = None,
    end: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Breakdown:
    return await DashboardService(container, session).breakdown(
        project.id, dimension, range, start, end, limit
    )
