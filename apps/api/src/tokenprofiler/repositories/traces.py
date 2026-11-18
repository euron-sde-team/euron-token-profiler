"""Traces and spans: the bulk write path, the filtered list and the detail read."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ColumnElement,
    String,
    and_,
    bindparam,
    delete,
    func,
    literal,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import ARRAY, insert

from tokenprofiler.ingest.attribution import Node
from tokenprofiler.models import Span, Trace
from tokenprofiler.repositories.base import Repository

# asyncpg takes at most 32767 bind parameters per statement.
SPAN_CHUNK = 400
TRACE_CHUNK = 1000
TOTAL_CAP = 10_000

SORTS: dict[str, Any] = {
    "started_at": Trace.started_at,
    "cost": Trace.total_cost,
    "duration": Trace.duration_ms,
    "tokens": Trace.total_tokens,
}


@dataclass(slots=True)
class TraceFilters:
    start: datetime | None = None
    end: datetime | None = None
    status: str | None = None
    query: str | None = None
    model: str | None = None
    agent: str | None = None
    tool: str | None = None
    prompt: str | None = None
    environment: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    tag: str | None = None
    min_cost: Decimal | None = None
    min_duration_ms: int | None = None
    extra: list[ColumnElement[bool]] = field(default_factory=list)


def _like(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _conditions(project_id: uuid.UUID, f: TraceFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [Trace.project_id == project_id]
    if f.start:
        conditions.append(Trace.started_at >= f.start)
    if f.end:
        conditions.append(Trace.started_at < f.end)
    if f.status:
        conditions.append(Trace.status == f.status)
    if f.query:
        needle = f.query.strip()
        conditions.append(
            or_(
                Trace.name.ilike(_like(needle)),
                Trace.id.startswith(needle),
                Trace.user_id == needle,
                Trace.session_id == needle,
            )
        )
    for column, value in (
        (Trace.models, f.model),
        (Trace.agents, f.agent),
        (Trace.tools, f.tool),
        (Trace.prompts, f.prompt),
        (Trace.tags, f.tag),
    ):
        if value:
            conditions.append(column.contains(literal([value], ARRAY(String))))
    if f.environment:
        conditions.append(Trace.environment == f.environment)
    if f.user_id:
        conditions.append(Trace.user_id == f.user_id)
    if f.session_id:
        conditions.append(Trace.session_id == f.session_id)
    if f.min_cost is not None:
        conditions.append(Trace.total_cost >= f.min_cost)
    if f.min_duration_ms is not None:
        conditions.append(Trace.duration_ms >= f.min_duration_ms)
    return [*conditions, *f.extra]


_REFRESH = text(
    """
    UPDATE traces t SET
      started_at = a.started_at,
      ended_at = a.ended_at,
      duration_ms = a.duration_ms,
      status = a.status,
      span_count = a.span_count,
      error_count = a.error_count,
      generation_count = a.generation_count,
      input_tokens = a.input_tokens,
      output_tokens = a.output_tokens,
      total_tokens = a.total_tokens,
      total_cost = a.total_cost,
      models = a.models,
      agents = a.agents,
      tools = a.tools,
      prompts = a.prompts,
      name = CASE WHEN t.name = '' THEN coalesce(a.root_name, '') ELSE t.name END
    FROM (
      SELECT trace_id,
        min(started_at) AS started_at,
        max(ended_at) AS ended_at,
        (extract(epoch FROM max(ended_at) - min(started_at)) * 1000)::int AS duration_ms,
        CASE WHEN bool_or(status = 'error') THEN 'error' ELSE 'ok' END AS status,
        count(*)::int AS span_count,
        (count(*) FILTER (WHERE status = 'error'))::int AS error_count,
        (count(*) FILTER (WHERE kind IN ('generation', 'embedding')))::int AS generation_count,
        coalesce(sum(input_tokens) FILTER (WHERE kind IN ('generation', 'embedding')), 0)
          AS input_tokens,
        coalesce(sum(output_tokens) FILTER (WHERE kind IN ('generation', 'embedding')), 0)
          AS output_tokens,
        coalesce(sum(total_tokens) FILTER (WHERE kind IN ('generation', 'embedding')), 0)
          AS total_tokens,
        coalesce(sum(total_cost) FILTER (WHERE kind IN ('generation', 'embedding')), 0)
          AS total_cost,
        coalesce(array_agg(DISTINCT model) FILTER (WHERE model IS NOT NULL), '{}') AS models,
        coalesce(array_agg(DISTINCT agent_name) FILTER (WHERE agent_name IS NOT NULL), '{}')
          AS agents,
        coalesce(array_agg(DISTINCT tool_name) FILTER (WHERE tool_name IS NOT NULL), '{}')
          AS tools,
        coalesce(array_agg(DISTINCT prompt_name) FILTER (WHERE prompt_name IS NOT NULL), '{}')
          AS prompts,
        (array_agg(name ORDER BY started_at) FILTER (WHERE parent_id IS NULL))[1] AS root_name
      FROM spans
      WHERE project_id = :project_id AND trace_id = ANY(:trace_ids)
      GROUP BY trace_id
    ) a
    WHERE t.project_id = :project_id AND t.id = a.trace_id
    """
).bindparams(bindparam("trace_ids", type_=ARRAY(String)))


class TraceRepository(Repository):
    async def upsert_traces(self, rows: Sequence[dict[str, Any]]) -> None:
        for start in range(0, len(rows), TRACE_CHUNK):
            statement = insert(Trace).values(list(rows[start : start + TRACE_CHUNK]))
            new = statement.excluded
            await self.session.execute(
                statement.on_conflict_do_update(
                    index_elements=[Trace.project_id, Trace.id],
                    set_={
                        "name": func.coalesce(func.nullif(new.name, ""), Trace.name),
                        "user_id": func.coalesce(new.user_id, Trace.user_id),
                        "session_id": func.coalesce(new.session_id, Trace.session_id),
                        "environment": func.coalesce(
                            func.nullif(new.environment, "default"), Trace.environment
                        ),
                        "release": func.coalesce(new.release, Trace.release),
                        "tags": text(
                            "CASE WHEN cardinality(excluded.tags) > 0 THEN excluded.tags "
                            "ELSE traces.tags END"
                        ),
                        "input": func.coalesce(new.input, Trace.input),
                        "output": func.coalesce(new.output, Trace.output),
                        "metadata": Trace.metadata_.op("||")(new.metadata),
                        "started_at": func.least(new.started_at, Trace.started_at),
                        "ended_at": func.greatest(new.ended_at, Trace.ended_at),
                    },
                )
            )

    async def upsert_spans(self, rows: Sequence[dict[str, Any]]) -> None:
        for start in range(0, len(rows), SPAN_CHUNK):
            statement = insert(Span).values(list(rows[start : start + SPAN_CHUNK]))
            replace = {
                column.name: statement.excluded[column.name]
                for column in Span.__table__.columns
                if not column.primary_key
            }
            await self.session.execute(
                statement.on_conflict_do_update(
                    index_elements=[Span.project_id, Span.trace_id, Span.id], set_=replace
                )
            )

    async def span_nodes(self, project_id: uuid.UUID, trace_ids: Sequence[str]) -> list[Node]:
        result = await self.session.execute(
            select(
                Span.id, Span.parent_id, Span.kind, Span.name, Span.agent_name, Span.tool_name
            ).where(Span.project_id == project_id, Span.trace_id.in_(trace_ids))
        )
        return [Node(*row) for row in result.all()]

    async def span_nodes_by_trace(
        self, project_id: uuid.UUID, trace_ids: Sequence[str]
    ) -> dict[str, list[Node]]:
        result = await self.session.execute(
            select(
                Span.trace_id,
                Span.id,
                Span.parent_id,
                Span.kind,
                Span.name,
                Span.agent_name,
                Span.tool_name,
            ).where(Span.project_id == project_id, Span.trace_id.in_(trace_ids))
        )
        grouped: dict[str, list[Node]] = {}
        for trace_id, span_id, parent_id, kind, name, agent, tool in result.all():
            grouped.setdefault(trace_id, []).append(
                Node(span_id, parent_id, kind, name, agent, tool)
            )
        return grouped

    async def apply_attribution(self, rows: list[dict[str, Any]]) -> None:
        """Bulk update by primary key: the keys carry the identity, the rest the new values."""
        if rows:
            await self.session.execute(update(Span), rows)

    async def refresh_aggregates(self, project_id: uuid.UUID, trace_ids: Sequence[str]) -> None:
        for start in range(0, len(trace_ids), TRACE_CHUNK):
            await self.session.execute(
                _REFRESH,
                {
                    "project_id": project_id,
                    "trace_ids": list(trace_ids[start : start + TRACE_CHUNK]),
                },
            )

    async def page(
        self,
        project_id: uuid.UUID,
        filters: TraceFilters,
        *,
        sort: str,
        descending: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Trace], int, bool]:
        """A page, the (capped) match count and whether the count was capped."""
        conditions = _conditions(project_id, filters)
        column = SORTS.get(sort, Trace.started_at)
        order = column.desc() if descending else column.asc()
        result = await self.session.execute(
            select(Trace).where(*conditions).order_by(order, Trace.id).limit(limit).offset(offset)
        )
        # Counting every match of a broad filter on a big table is slow and nobody reads
        # past a few thousand: count at most one more than the cap.
        counted = await self.session.scalar(
            select(func.count()).select_from(
                select(literal(1))
                .select_from(Trace)
                .where(and_(*conditions))
                .limit(TOTAL_CAP + 1)
                .subquery()
            )
        )
        total = int(counted or 0)
        return list(result.scalars()), min(total, TOTAL_CAP), total > TOTAL_CAP

    async def get(self, project_id: uuid.UUID, trace_id: str) -> Trace | None:
        return await self.session.get(Trace, (project_id, trace_id))

    async def spans(self, project_id: uuid.UUID, trace_id: str) -> list[Span]:
        result = await self.session.execute(
            select(Span)
            .where(Span.project_id == project_id, Span.trace_id == trace_id)
            .order_by(Span.started_at, Span.id)
        )
        return list(result.scalars())

    async def expired_ids(self, project_id: uuid.UUID, cutoff: datetime, limit: int) -> list[str]:
        result = await self.session.execute(
            select(Trace.id)
            .where(Trace.project_id == project_id, Trace.started_at < cutoff)
            .order_by(Trace.started_at)
            .limit(limit)
        )
        return [row[0] for row in result]

    async def with_spans(
        self, project_id: uuid.UUID, trace_ids: Sequence[str]
    ) -> list[tuple[Trace, list[Span]]]:
        traces = await self.session.execute(
            select(Trace).where(Trace.project_id == project_id, Trace.id.in_(trace_ids))
        )
        spans = await self.session.execute(
            select(Span)
            .where(Span.project_id == project_id, Span.trace_id.in_(trace_ids))
            .order_by(Span.started_at, Span.id)
        )
        grouped: dict[str, list[Span]] = {}
        for span in spans.scalars():
            grouped.setdefault(span.trace_id, []).append(span)
        return [(trace, grouped.get(trace.id, [])) for trace in traces.scalars()]

    async def delete(self, project_id: uuid.UUID, trace_ids: Sequence[str]) -> int:
        """Delete traces; their spans go with them (ON DELETE CASCADE)."""
        result = await self.session.execute(
            delete(Trace).where(Trace.project_id == project_id, Trace.id.in_(trace_ids))
        )
        return int(result.rowcount or 0)  # type: ignore[attr-defined]

    async def facets(self, project_id: uuid.UUID, since: datetime) -> dict[str, list[str]]:
        """Distinct values for the filter menus, from the recent window only."""
        out: dict[str, list[str]] = {}
        # The column names come from this fixed list, never from a request.
        for name in ("models", "agents", "tools", "prompts", "tags"):
            result = await self.session.execute(
                text(
                    f"SELECT DISTINCT v FROM traces, unnest({name}) AS v "  # noqa: S608
                    "WHERE project_id = :project_id AND started_at >= :since "
                    "ORDER BY v LIMIT 200"
                ),
                {"project_id": project_id, "since": since},
            )
            out[name] = [row[0] for row in result]
        environments = await self.session.execute(
            select(Trace.environment)
            .where(Trace.project_id == project_id, Trace.started_at >= since)
            .distinct()
            .order_by(Trace.environment)
            .limit(50)
        )
        out["environments"] = [row[0] for row in environments]
        return out
