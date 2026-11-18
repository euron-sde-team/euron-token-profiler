"""The native ingest protocol (what the Python SDK sends) and the ingest response."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from tokenprofiler.schemas.common import ApiModel

Id = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")]
SpanId = Annotated[
    str, StringConstraints(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_.:-]+$")
]
Label = Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class UsagePayload(ApiModel):
    input: int | None = Field(default=None, ge=0, le=10**10)
    output: int | None = Field(default=None, ge=0, le=10**10)
    cached: int | None = Field(
        default=None, ge=0, le=10**10, description="Input tokens read from a cache."
    )


class CostPayload(ApiModel):
    input: Decimal | None = Field(default=None, ge=0)
    output: Decimal | None = Field(default=None, ge=0)
    total: Decimal | None = Field(default=None, ge=0)


class PromptRefPayload(ApiModel):
    name: Label
    version: int = Field(ge=1, le=1_000_000)


class SpanPayload(ApiModel):
    id: SpanId
    trace_id: Id
    parent_id: SpanId | None = None
    name: Label
    kind: Literal["span", "generation", "embedding", "agent", "tool", "retriever"] = "span"
    start_time: datetime
    end_time: datetime | None = None
    status: Literal["ok", "error"] = "ok"
    status_message: str | None = Field(default=None, max_length=2000)
    level: Literal["debug", "default", "warning", "error"] = "default"
    model: Annotated[str, StringConstraints(max_length=160)] | None = None
    provider: Annotated[str, StringConstraints(max_length=48)] | None = None
    model_parameters: dict[str, Any] = Field(default_factory=dict)
    usage: UsagePayload | None = None
    cost: CostPayload | None = None
    time_to_first_token_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    agent: Label | None = Field(default=None, description="Names the agent this span belongs to.")
    tool: Label | None = Field(default=None, description="Names the tool this span belongs to.")
    prompt: PromptRefPayload | None = None
    input: Any = None
    output: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _times(self) -> Self:
        self.start_time = _aware(self.start_time)
        end = _aware(self.end_time) if self.end_time else self.start_time
        self.end_time = max(end, self.start_time)
        return self


class TracePayload(ApiModel):
    id: Id
    name: Label | None = None
    user_id: Annotated[str, StringConstraints(max_length=128)] | None = None
    session_id: Annotated[str, StringConstraints(max_length=128)] | None = None
    environment: Annotated[str, StringConstraints(min_length=1, max_length=48)] | None = None
    release: Annotated[str, StringConstraints(max_length=64)] | None = None
    tags: list[Annotated[str, StringConstraints(min_length=1, max_length=48)]] = Field(
        default_factory=list, max_length=30
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    input: Any = None
    output: Any = None
    timestamp: datetime | None = None


class IngestBatch(ApiModel):
    """Items are validated one by one: a bad span is reported and the rest are stored."""

    traces: list[dict[str, Any]] = Field(default_factory=list)
    spans: list[dict[str, Any]] = Field(default_factory=list)


class IngestResult(ApiModel):
    accepted_spans: int
    accepted_traces: int
    sampled_out_traces: int = 0
    redactions: int = 0
    rejected: list[str] = Field(default_factory=list)
