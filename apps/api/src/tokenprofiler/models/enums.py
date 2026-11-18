"""Value sets stored as text with CHECK constraints (cheaper to evolve than Postgres enums)."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"  # everything, including people, projects, redaction and retention
    MEMBER = "member"  # prompts, budgets, alert rules, prices and project keys
    VIEWER = "viewer"  # read only

    @property
    def can_write(self) -> bool:
        return self in {Role.ADMIN, Role.MEMBER}


class SpanKind(StrEnum):
    SPAN = "span"
    GENERATION = "generation"  # one model call: carries model, usage and cost
    EMBEDDING = "embedding"
    AGENT = "agent"  # one run of an agent; everything below it is attributed to it
    TOOL = "tool"  # a tool call; model calls nested inside are attributed to it
    RETRIEVER = "retriever"

    @property
    def metered(self) -> bool:
        """Only these kinds carry token usage and cost (parents never double count)."""
        return self in {SpanKind.GENERATION, SpanKind.EMBEDDING}


class Status(StrEnum):
    OK = "ok"
    ERROR = "error"


class PriceSource(StrEnum):
    BUILTIN = "builtin"  # shipped with TokenProfiler and refreshed on upgrade
    CUSTOM = "custom"  # a global or per-project override entered by a person


class BudgetScope(StrEnum):
    PROJECT = "project"
    MODEL = "model"
    AGENT = "agent"
    TOOL = "tool"
    PROMPT = "prompt"


class BudgetPeriod(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class RuleMetric(StrEnum):
    ERROR_RATE = "error_rate"  # percent of traces that failed in the window
    P95_LATENCY_MS = "p95_latency_ms"  # 95th percentile trace duration
    COST_USD = "cost_usd"  # spend in the window
    TRACE_COUNT = "trace_count"  # traces in the window (a low value means silence)


class RuleComparator(StrEnum):
    ABOVE = "above"
    BELOW = "below"


class AlertKind(StrEnum):
    BUDGET = "budget"
    RULE = "rule"


class AlertSeverity(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"


class AlertState(StrEnum):
    FIRING = "firing"
    RESOLVED = "resolved"
