from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from tokenprofiler.schemas.common import ApiModel

Name = Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]


class BudgetWrite(ApiModel):
    name: Name
    scope: Literal["project", "model", "agent", "tool", "prompt"] = "project"
    scope_value: Annotated[str, StringConstraints(min_length=1, max_length=160)] | None = None
    period: Literal["day", "week", "month"] = "month"
    limit_usd: Decimal = Field(gt=0, le=10_000_000, max_digits=14, decimal_places=4)
    warn_at_percent: int = Field(default=80, ge=1, le=100)
    enabled: bool = True

    @model_validator(mode="after")
    def _scope(self) -> Self:
        if (self.scope == "project") != (self.scope_value is None):
            raise ValueError("A project budget has no scope value; every other scope needs one.")
        return self


class BudgetOut(ApiModel):
    id: uuid.UUID
    name: str
    scope: str
    scope_value: str | None
    period: str
    limit_usd: Decimal
    warn_at_percent: int
    enabled: bool
    spent_usd: Decimal
    percent_used: float
    period_start: datetime
    period_end: datetime
    state: Literal["ok", "warning", "exceeded"]


class RuleWrite(ApiModel):
    name: Name
    metric: Literal["error_rate", "p95_latency_ms", "cost_usd", "trace_count"]
    comparator: Literal["above", "below"] = "above"
    threshold: Decimal = Field(ge=0, le=1_000_000_000, max_digits=18, decimal_places=4)
    window_minutes: int = Field(default=60, ge=1, le=10_080)
    min_traces: int = Field(default=10, ge=0, le=1_000_000)
    severity: Literal["warning", "critical"] = "warning"
    enabled: bool = True


class RuleOut(ApiModel):
    id: uuid.UUID
    name: str
    metric: str
    comparator: str
    threshold: Decimal
    window_minutes: int
    min_traces: int
    severity: str
    enabled: bool
    firing: bool = False


class AlertEventOut(ApiModel):
    id: uuid.UUID
    kind: str
    source_id: uuid.UUID
    source_name: str
    severity: str
    state: str
    value: Decimal
    threshold: Decimal
    message: str
    fired_at: datetime
    resolved_at: datetime | None
    notified_at: datetime | None
    notify_error: str | None


class AlertsOverview(ApiModel):
    budgets: list[BudgetOut]
    rules: list[RuleOut]
    firing: int
