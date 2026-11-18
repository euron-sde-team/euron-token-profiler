from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from tokenprofiler.schemas.common import ApiModel


class KpiOut(ApiModel):
    traces: int
    errors: int
    error_rate: float
    cost: Decimal
    input_tokens: int
    output_tokens: int
    generations: int
    users: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_cost_per_trace: Decimal


class PointOut(ApiModel):
    at: datetime
    traces: int
    errors: int
    error_rate: float
    cost: Decimal
    input_tokens: int
    output_tokens: int
    p50_ms: float
    p95_ms: float


class CostSlice(ApiModel):
    key: str
    cost: Decimal


class CostPoint(ApiModel):
    at: datetime
    values: dict[str, Decimal]


class Overview(ApiModel):
    start: datetime
    end: datetime
    bucket_seconds: int
    current: KpiOut
    previous: KpiOut
    series: list[PointOut]
    cost_by_model: list[CostPoint]
    top_models: list[str]
    generated_at: datetime
    cached: bool = False


class BreakdownItem(ApiModel):
    key: str
    version: int | None = None
    calls: int
    errors: int
    error_rate: float
    p50_ms: float
    p95_ms: float
    generations: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost: Decimal
    cost_share: float
    avg_cost_per_call: Decimal
    avg_ttft_ms: float | None
    last_seen: datetime


class Breakdown(ApiModel):
    dimension: str
    start: datetime
    end: datetime
    total_cost: Decimal
    items: list[BreakdownItem]
    generated_at: datetime
    cached: bool = False
