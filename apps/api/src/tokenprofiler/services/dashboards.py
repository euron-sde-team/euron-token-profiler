"""Dashboard aggregates, cached in Valkey.

A dashboard is read far more often than its numbers change, and each read costs several
aggregate queries. Results are cached per project, endpoint and normalised parameters for
`dashboard_cache_ttl_s` seconds. Relative ranges ("last 24 hours") end on a 30 second
boundary so that every viewer in that half minute asks for the same window and shares one
cache entry. Keys always carry the project id, so one project can never be served another's
numbers.
"""

from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from tokenprofiler.core import metrics
from tokenprofiler.core.errors import UnprocessableError
from tokenprofiler.repositories.metrics import DIMENSIONS, Kpis, MetricsRepository, SeriesPoint
from tokenprofiler.schemas.metrics import (
    Breakdown,
    BreakdownItem,
    CostPoint,
    KpiOut,
    Overview,
    PointOut,
)
from tokenprofiler.services.container import Container

RANGES: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "14d": timedelta(days=14),
    "30d": timedelta(days=30),
}
BUCKETS = [
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=30),
    timedelta(hours=1),
    timedelta(hours=3),
    timedelta(hours=6),
    timedelta(hours=12),
    timedelta(days=1),
]
TARGET_POINTS = 72
TOP_MODELS = 5
SNAP_S = 30


def bucket_for(span: timedelta) -> timedelta:
    """The smallest standard bucket that keeps a chart near TARGET_POINTS points."""
    wanted = span / TARGET_POINTS
    return next((b for b in BUCKETS if b >= wanted), BUCKETS[-1])


def resolve_window(
    range_key: str | None, start: datetime | None, end: datetime | None, *, now: datetime
) -> tuple[datetime, datetime]:
    if start is not None:
        stop = end or now
        if stop <= start:
            raise UnprocessableError("The end of the range must be after its start.")
        if stop - start > timedelta(days=366):
            raise UnprocessableError("Use a range of at most a year.")
        return start, stop
    key = range_key or "24h"
    if key not in RANGES:
        raise UnprocessableError(f"Use one of: {', '.join(RANGES)}.")
    snapped = datetime.fromtimestamp(int(now.timestamp()) // SNAP_S * SNAP_S, UTC)
    return snapped - RANGES[key], snapped


def _kpi(k: Kpis) -> KpiOut:
    return KpiOut(
        traces=k.traces,
        errors=k.errors,
        error_rate=round(100 * k.errors / k.traces, 2) if k.traces else 0.0,
        cost=k.cost,
        input_tokens=k.input_tokens,
        output_tokens=k.output_tokens,
        generations=k.generations,
        users=k.users,
        p50_ms=round(k.p50_ms),
        p95_ms=round(k.p95_ms),
        p99_ms=round(k.p99_ms),
        avg_cost_per_trace=(k.cost / k.traces).quantize(Decimal("0.00000001"))
        if k.traces
        else Decimal(0),
    )


def _fill(
    points: list[SeriesPoint], start: datetime, end: datetime, bucket: timedelta
) -> list[PointOut]:
    """One point per bucket, zeros where nothing happened, so charts have no gaps."""
    by_time = {p.at: p for p in points}
    origin = datetime(2000, 1, 1, tzinfo=UTC)
    first = origin + ((start - origin) // bucket) * bucket
    out: list[PointOut] = []
    cursor = first
    while cursor < end:
        p = by_time.get(cursor)
        out.append(
            PointOut(
                at=cursor,
                traces=p.traces if p else 0,
                errors=p.errors if p else 0,
                error_rate=round(100 * p.errors / p.traces, 2) if p and p.traces else 0.0,
                cost=p.cost if p else Decimal(0),
                input_tokens=p.input_tokens if p else 0,
                output_tokens=p.output_tokens if p else 0,
                p50_ms=round(p.p50_ms) if p else 0,
                p95_ms=round(p.p95_ms) if p else 0,
            )
        )
        cursor += bucket
    return out


class DashboardService:
    def __init__(self, container: Container, session: AsyncSession) -> None:
        self.c = container
        self.metrics = MetricsRepository(session)

    async def _cached[T: Overview | Breakdown](
        self,
        model: type[T],
        project_id: uuid.UUID,
        kind: str,
        params: str,
        compute: Callable[[], Awaitable[T]],
    ) -> T:
        ttl = self.c.settings.dashboard_cache_ttl_s
        digest = hashlib.sha1(params.encode(), usedforsecurity=False).hexdigest()
        key = f"dash:{project_id}:{kind}:{digest}"
        if ttl > 0 and (raw := await self.c.redis.get(key)):
            metrics.DASHBOARD_CACHE.labels("hit").inc()
            cached = TypeAdapter(model).validate_json(raw)
            cached.cached = True
            return cached
        metrics.DASHBOARD_CACHE.labels("miss").inc()
        result = await compute()
        if ttl > 0:
            await self.c.redis.set(key, result.model_dump_json(), ex=ttl)
        return result

    async def overview(
        self,
        project_id: uuid.UUID,
        range_key: str | None,
        start: datetime | None,
        end: datetime | None,
        environment: str | None,
    ) -> Overview:
        now = datetime.now(UTC)
        window_start, window_end = resolve_window(range_key, start, end, now=now)
        params = f"{window_start.isoformat()}|{window_end.isoformat()}|{environment}"
        return await self._cached(
            Overview,
            project_id,
            "overview",
            params,
            lambda: self._overview(project_id, window_start, window_end, environment),
        )

    async def _overview(
        self, project_id: uuid.UUID, start: datetime, end: datetime, environment: str | None
    ) -> Overview:
        span = end - start
        bucket = bucket_for(span)
        current = await self.metrics.kpis(project_id, start, end, environment)
        previous = await self.metrics.kpis(project_id, start - span, start, environment)
        series = await self.metrics.series(project_id, start, end, bucket, environment)
        rows = await self.metrics.cost_series(project_id, "model", start, end, bucket, environment)
        totals: dict[str, Decimal] = defaultdict(Decimal)
        for _, key, cost in rows:
            totals[key] += cost
        top = [k for k, _ in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)][
            :TOP_MODELS
        ]
        grouped: dict[datetime, dict[str, Decimal]] = defaultdict(dict)
        for at, key, cost in rows:
            label = key if key in top else "other"
            grouped[at][label] = grouped[at].get(label, Decimal(0)) + cost
        origin = datetime(2000, 1, 1, tzinfo=UTC)
        cursor = origin + ((start - origin) // bucket) * bucket
        cost_points: list[CostPoint] = []
        while cursor < end:
            cost_points.append(CostPoint(at=cursor, values=grouped.get(cursor, {})))
            cursor += bucket
        has_other = any("other" in point.values for point in cost_points)
        return Overview(
            start=start,
            end=end,
            bucket_seconds=int(bucket.total_seconds()),
            current=_kpi(current),
            previous=_kpi(previous),
            series=_fill(series, start, end, bucket),
            cost_by_model=cost_points,
            top_models=[*top, "other"] if has_other else top,
            generated_at=datetime.now(UTC),
        )

    async def breakdown(
        self,
        project_id: uuid.UUID,
        dimension: str,
        range_key: str | None,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> Breakdown:
        if dimension not in DIMENSIONS:
            raise UnprocessableError(f"Use one of: {', '.join(DIMENSIONS)}.")
        window_start, window_end = resolve_window(range_key, start, end, now=datetime.now(UTC))
        params = f"{dimension}|{window_start.isoformat()}|{window_end.isoformat()}|{limit}"
        return await self._cached(
            Breakdown,
            project_id,
            "breakdown",
            params,
            lambda: self._breakdown(project_id, dimension, window_start, window_end, limit),
        )

    async def _breakdown(
        self, project_id: uuid.UUID, dimension: str, start: datetime, end: datetime, limit: int
    ) -> Breakdown:
        rows = await self.metrics.breakdown(project_id, dimension, start, end, limit=limit)
        total = sum((row.cost for row in rows), Decimal(0))
        items = [
            BreakdownItem(
                key=row.key,
                version=row.version,
                calls=row.calls,
                errors=row.errors,
                error_rate=round(100 * row.errors / row.calls, 2) if row.calls else 0.0,
                p50_ms=round(row.p50_ms),
                p95_ms=round(row.p95_ms),
                generations=row.generations,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                cached_tokens=row.cached_tokens,
                cost=row.cost,
                cost_share=round(float(row.cost / total), 4) if total else 0.0,
                avg_cost_per_call=(row.cost / row.calls).quantize(Decimal("0.00000001"))
                if row.calls
                else Decimal(0),
                avg_ttft_ms=None if row.avg_ttft_ms is None else round(row.avg_ttft_ms),
                last_seen=row.last_seen,
            )
            for row in rows
        ]
        return Breakdown(
            dimension=dimension,
            start=start,
            end=end,
            total_cost=total,
            items=items,
            generated_at=datetime.now(UTC),
        )
