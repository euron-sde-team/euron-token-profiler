"""Traces: the filtered list, the detail with spans, and the filter menus."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from tokenprofiler.api.deps import ProjectDep, SessionDep
from tokenprofiler.repositories.traces import TraceFilters
from tokenprofiler.schemas.traces import Facets, TracePage, TraceWithSpans
from tokenprofiler.services.dashboards import resolve_window
from tokenprofiler.services.traces import TraceService

router = APIRouter(prefix="/api/v1/projects/{project_id}/traces", tags=["traces"])


@router.get("", summary="Traces, newest first, with filters and search")
async def list_traces(
    project: ProjectDep,
    session: SessionDep,
    range: Annotated[str | None, Query(description="1h, 6h, 24h, 7d, 14d or 30d")] = "24h",
    start: datetime | None = None,
    end: datetime | None = None,
    status: Literal["ok", "error"] | None = None,
    q: Annotated[
        str | None, Query(max_length=200, description="Name, id prefix, user or session")
    ] = None,
    model: Annotated[str | None, Query(max_length=160)] = None,
    agent: Annotated[str | None, Query(max_length=120)] = None,
    tool: Annotated[str | None, Query(max_length=120)] = None,
    prompt: Annotated[str | None, Query(max_length=120)] = None,
    environment: Annotated[str | None, Query(max_length=48)] = None,
    user_id: Annotated[str | None, Query(max_length=128)] = None,
    session_id: Annotated[str | None, Query(max_length=128)] = None,
    tag: Annotated[str | None, Query(max_length=48)] = None,
    min_cost: Annotated[Decimal | None, Query(ge=0)] = None,
    min_duration_ms: Annotated[int | None, Query(ge=0)] = None,
    sort: Literal["started_at", "cost", "duration", "tokens"] = "started_at",
    order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> TracePage:
    window_start, window_end = resolve_window(range, start, end, now=datetime.now(UTC))
    filters = TraceFilters(
        start=window_start,
        # A relative range is open ended: the list is not cached, and a trace that arrived a
        # moment ago must show up even though the dashboards snap their window to 30 seconds.
        end=window_end if (start is not None or end is not None) else None,
        status=status,
        query=q,
        model=model,
        agent=agent,
        tool=tool,
        prompt=prompt,
        environment=environment,
        user_id=user_id,
        session_id=session_id,
        tag=tag,
        min_cost=min_cost,
        min_duration_ms=min_duration_ms,
    )
    return await TraceService(session).page(
        project.id, filters, sort=sort, descending=order == "desc", limit=limit, offset=offset
    )


@router.get("/facets", summary="Values for the filter menus (last 30 days)")
async def facets(project: ProjectDep, session: SessionDep) -> Facets:
    return await TraceService(session).facets(project.id)


@router.get("/{trace_id}", summary="One trace with every span")
async def get_trace(trace_id: str, project: ProjectDep, session: SessionDep) -> TraceWithSpans:
    return await TraceService(session).detail(project.id, trace_id)
