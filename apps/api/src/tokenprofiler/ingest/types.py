"""The normalised shape every ingest protocol is converted to before it is stored."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(slots=True)
class SpanIn:
    trace_id: str
    span_id: str
    parent_id: str | None
    name: str
    kind: str
    started_at: datetime
    ended_at: datetime
    status: str = "ok"
    status_message: str | None = None
    level: str = "default"
    model: str | None = None
    provider: str | None = None
    model_parameters: dict[str, Any] = field(default_factory=dict)
    # None means "not reported": the price table or the estimator may fill it in.
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    reported_cost: Decimal | None = None
    reported_input_cost: Decimal | None = None
    reported_output_cost: Decimal | None = None
    time_to_first_token_ms: int | None = None
    agent_name: str | None = None
    tool_name: str | None = None
    prompt_name: str | None = None
    prompt_version: int | None = None
    input: Any = None
    output: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    # Trace-level fields that arrive on a span (OpenTelemetry has no separate trace record).
    trace_name: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    environment: str | None = None
    release: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TraceIn:
    """Trace-level fields sent on their own (the native protocol)."""

    trace_id: str
    name: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    environment: str | None = None
    release: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    input: Any = None
    output: Any = None
    timestamp: datetime | None = None


@dataclass(slots=True)
class Batch:
    spans: list[SpanIn] = field(default_factory=list)
    traces: list[TraceIn] = field(default_factory=list)
    # Spans the parser could not use (missing ids, bad timestamps) and why.
    rejected: list[str] = field(default_factory=list)
