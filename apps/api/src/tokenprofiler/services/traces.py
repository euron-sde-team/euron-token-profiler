"""Reading traces: the filtered list, one trace with its spans, and the filter menus."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from tokenprofiler.core.errors import NotFoundError
from tokenprofiler.repositories.traces import TraceFilters, TraceRepository
from tokenprofiler.schemas.traces import (
    Facets,
    SpanOut,
    TraceDetail,
    TraceOut,
    TracePage,
    TraceWithSpans,
)

FACET_WINDOW = timedelta(days=30)


class TraceService:
    def __init__(self, session: AsyncSession) -> None:
        self.traces = TraceRepository(session)

    async def page(
        self,
        project_id: uuid.UUID,
        filters: TraceFilters,
        *,
        sort: str,
        descending: bool,
        limit: int,
        offset: int,
    ) -> TracePage:
        rows, total, capped = await self.traces.page(
            project_id, filters, sort=sort, descending=descending, limit=limit, offset=offset
        )
        return TracePage(
            items=[TraceOut.model_validate(row) for row in rows],
            total=total,
            total_capped=capped,
            limit=limit,
            offset=offset,
        )

    async def detail(self, project_id: uuid.UUID, trace_id: str) -> TraceWithSpans:
        trace = await self.traces.get(project_id, trace_id)
        if trace is None:
            raise NotFoundError("Trace not found. It may have been sampled out or expired.")
        spans = await self.traces.spans(project_id, trace_id)
        return TraceWithSpans(
            trace=TraceDetail.model_validate(trace),
            spans=[SpanOut.model_validate(span) for span in spans],
        )

    async def facets(self, project_id: uuid.UUID) -> Facets:
        data = await self.traces.facets(project_id, datetime.now(UTC) - FACET_WINDOW)
        return Facets(**data)
