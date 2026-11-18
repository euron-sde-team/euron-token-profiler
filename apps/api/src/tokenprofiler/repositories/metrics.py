"""Aggregates for the dashboards, budgets and alert rules.

Traces carry denormalised totals, so the overview reads one narrow table. Breakdowns by
model, agent, tool and prompt read spans through partial indexes on (project, key, time).
Column names that reach SQL text come from the fixed tables below, never from a request.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from tokenprofiler.repositories.base import Repository

METERED = "kind IN ('generation', 'embedding')"
ORIGIN = datetime.fromisoformat("2000-01-01T00:00:00+00:00")

# dimension -> (key expression, filter for rows that carry it, predicate that counts a "call")
DIMENSIONS: dict[str, tuple[str, str, str]] = {
    "model": ("model", "model IS NOT NULL", METERED),
    "agent": ("agent_name", "agent_name IS NOT NULL", "kind = 'agent'"),
    "tool": ("tool_name", "tool_name IS NOT NULL", "kind = 'tool'"),
    "prompt": ("prompt_name", "prompt_name IS NOT NULL", METERED),
}


@dataclass(frozen=True, slots=True)
class Kpis:
    traces: int
    errors: int
    cost: Decimal
    input_tokens: int
    output_tokens: int
    generations: int
    users: int
    p50_ms: float
    p95_ms: float
    p99_ms: float


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    at: datetime
    traces: int
    errors: int
    cost: Decimal
    input_tokens: int
    output_tokens: int
    p50_ms: float
    p95_ms: float


@dataclass(frozen=True, slots=True)
class BreakdownRow:
    key: str
    version: int | None
    calls: int
    errors: int
    p50_ms: float
    p95_ms: float
    generations: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost: Decimal
    avg_ttft_ms: float | None
    last_seen: datetime


def _f(value: Any) -> float:
    return float(value) if value is not None else 0.0


class MetricsRepository(Repository):
    async def kpis(
        self, project_id: uuid.UUID, start: datetime, end: datetime, environment: str | None
    ) -> Kpis:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT count(*) AS traces,
                      count(*) FILTER (WHERE status = 'error') AS errors,
                      coalesce(sum(total_cost), 0) AS cost,
                      coalesce(sum(input_tokens), 0) AS input_tokens,
                      coalesce(sum(output_tokens), 0) AS output_tokens,
                      coalesce(sum(generation_count), 0) AS generations,
                      count(DISTINCT user_id) AS users,
                      percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_ms) AS p50,
                      percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95,
                      percentile_cont(0.99) WITHIN GROUP (ORDER BY duration_ms) AS p99
                    FROM traces
                    WHERE project_id = :project_id AND started_at >= :start AND started_at < :end
                      AND (CAST(:environment AS text) IS NULL OR environment = :environment)
                    """
                ),
                {"project_id": project_id, "start": start, "end": end, "environment": environment},
            )
        ).one()
        return Kpis(
            traces=int(row.traces),
            errors=int(row.errors),
            cost=Decimal(row.cost),
            input_tokens=int(row.input_tokens),
            output_tokens=int(row.output_tokens),
            generations=int(row.generations),
            users=int(row.users),
            p50_ms=_f(row.p50),
            p95_ms=_f(row.p95),
            p99_ms=_f(row.p99),
        )

    async def series(
        self,
        project_id: uuid.UUID,
        start: datetime,
        end: datetime,
        bucket: timedelta,
        environment: str | None,
    ) -> list[SeriesPoint]:
        result = await self.session.execute(
            text(
                """
                SELECT date_bin(:bucket, started_at, :origin) AS at,
                  count(*) AS traces,
                  count(*) FILTER (WHERE status = 'error') AS errors,
                  coalesce(sum(total_cost), 0) AS cost,
                  coalesce(sum(input_tokens), 0) AS input_tokens,
                  coalesce(sum(output_tokens), 0) AS output_tokens,
                  percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_ms) AS p50,
                  percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95
                FROM traces
                WHERE project_id = :project_id AND started_at >= :start AND started_at < :end
                  AND (CAST(:environment AS text) IS NULL OR environment = :environment)
                GROUP BY 1 ORDER BY 1
                """
            ),
            {
                "project_id": project_id,
                "start": start,
                "end": end,
                "bucket": bucket,
                "origin": ORIGIN,
                "environment": environment,
            },
        )
        return [
            SeriesPoint(
                at=row.at,
                traces=int(row.traces),
                errors=int(row.errors),
                cost=Decimal(row.cost),
                input_tokens=int(row.input_tokens),
                output_tokens=int(row.output_tokens),
                p50_ms=_f(row.p50),
                p95_ms=_f(row.p95),
            )
            for row in result
        ]

    async def cost_series(
        self,
        project_id: uuid.UUID,
        dimension: str,
        start: datetime,
        end: datetime,
        bucket: timedelta,
        environment: str | None,
    ) -> list[tuple[datetime, str, Decimal]]:
        """Cost per bucket for each key of a dimension (model, agent, tool or prompt)."""
        key, present, _ = DIMENSIONS[dimension]
        result = await self.session.execute(
            text(
                f"""
                SELECT date_bin(:bucket, started_at, :origin) AS at, {key} AS key,
                  sum(total_cost) AS cost
                FROM spans
                WHERE project_id = :project_id AND started_at >= :start AND started_at < :end
                  AND {METERED} AND {present}
                GROUP BY 1, 2 ORDER BY 1
                """  # noqa: S608
            ),
            {
                "project_id": project_id,
                "start": start,
                "end": end,
                "bucket": bucket,
                "origin": ORIGIN,
            },
        )
        return [(row.at, row.key, Decimal(row.cost)) for row in result]

    async def breakdown(
        self,
        project_id: uuid.UUID,
        dimension: str,
        start: datetime,
        end: datetime,
        *,
        limit: int,
    ) -> list[BreakdownRow]:
        key, present, call = DIMENSIONS[dimension]
        group = f"{key}, prompt_version" if dimension == "prompt" else key
        version = "prompt_version" if dimension == "prompt" else "NULL::int"
        result = await self.session.execute(
            text(
                f"""
                SELECT {key} AS key, {version} AS version,
                  count(*) FILTER (WHERE {call}) AS calls,
                  count(*) FILTER (WHERE {call} AND status = 'error') AS errors,
                  coalesce(percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_ms)
                    FILTER (WHERE {call}), 0) AS p50,
                  coalesce(percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms)
                    FILTER (WHERE {call}), 0) AS p95,
                  count(*) FILTER (WHERE {METERED}) AS generations,
                  coalesce(sum(input_tokens) FILTER (WHERE {METERED}), 0) AS input_tokens,
                  coalesce(sum(output_tokens) FILTER (WHERE {METERED}), 0) AS output_tokens,
                  coalesce(sum(cached_tokens) FILTER (WHERE {METERED}), 0) AS cached_tokens,
                  coalesce(sum(total_cost) FILTER (WHERE {METERED}), 0) AS cost,
                  avg(time_to_first_token_ms) FILTER (WHERE {METERED}) AS ttft,
                  max(started_at) AS last_seen
                FROM spans
                WHERE project_id = :project_id AND started_at >= :start AND started_at < :end
                  AND {present}
                GROUP BY {group}
                ORDER BY cost DESC, calls DESC, key
                LIMIT :limit
                """  # noqa: S608
            ),
            {"project_id": project_id, "start": start, "end": end, "limit": limit},
        )
        return [
            BreakdownRow(
                key=row.key,
                version=row.version,
                calls=int(row.calls),
                errors=int(row.errors),
                p50_ms=_f(row.p50),
                p95_ms=_f(row.p95),
                generations=int(row.generations),
                input_tokens=int(row.input_tokens),
                output_tokens=int(row.output_tokens),
                cached_tokens=int(row.cached_tokens),
                cost=Decimal(row.cost),
                avg_ttft_ms=None if row.ttft is None else float(row.ttft),
                last_seen=row.last_seen,
            )
            for row in result
        ]

    async def spend(
        self,
        project_id: uuid.UUID,
        scope: str,
        value: str | None,
        since: datetime,
    ) -> Decimal:
        """Spend since a moment, for the whole project or narrowed to one key."""
        column = {
            "model": "model",
            "agent": "agent_name",
            "tool": "tool_name",
            "prompt": "prompt_name",
        }.get(scope)
        narrowing = f"AND {column} = :value" if column else ""
        total = await self.session.scalar(
            text(
                f"""
                SELECT coalesce(sum(total_cost), 0) FROM spans
                WHERE project_id = :project_id AND started_at >= :since AND {METERED} {narrowing}
                """  # noqa: S608
            ),
            {"project_id": project_id, "since": since, "value": value},
        )
        return Decimal(total or 0)

    async def window_stats(
        self, project_id: uuid.UUID, since: datetime
    ) -> tuple[int, int, float, Decimal]:
        """(traces, errors, p95 duration, spend) over a trailing window, for alert rules."""
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT count(*) AS traces,
                      count(*) FILTER (WHERE status = 'error') AS errors,
                      coalesce(percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms), 0) AS p95,
                      coalesce(sum(total_cost), 0) AS cost
                    FROM traces WHERE project_id = :project_id AND started_at >= :since
                    """
                ),
                {"project_id": project_id, "since": since},
            )
        ).one()
        return int(row.traces), int(row.errors), float(row.p95), Decimal(row.cost)
