from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from tokenprofiler.schemas.common import ApiModel, Page


class TraceOut(ApiModel):
    id: str
    name: str
    user_id: str | None
    session_id: str | None
    environment: str
    release: str | None
    tags: list[str]
    started_at: datetime
    ended_at: datetime
    duration_ms: int
    status: str
    span_count: int
    error_count: int
    generation_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    total_cost: Decimal
    models: list[str]
    agents: list[str]
    tools: list[str]
    prompts: list[str]


class TraceDetail(TraceOut):
    input: str | None
    output: str | None
    metadata: dict[str, Any] = Field(validation_alias="metadata_")


class SpanOut(ApiModel):
    id: str
    parent_id: str | None
    name: str
    kind: str
    started_at: datetime
    ended_at: datetime
    duration_ms: int
    time_to_first_token_ms: int | None
    status: str
    status_message: str | None
    level: str
    agent_name: str | None
    tool_name: str | None
    prompt_name: str | None
    prompt_version: int | None
    model: str | None
    provider: str | None
    model_parameters: dict[str, Any]
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    total_tokens: int
    usage_estimated: bool
    input_cost: Decimal
    output_cost: Decimal
    total_cost: Decimal
    cost_source: str | None
    input: str | None
    output: str | None
    metadata: dict[str, Any] = Field(validation_alias="metadata_")
    redactions: int


class TraceWithSpans(ApiModel):
    trace: TraceDetail
    spans: list[SpanOut]


class TracePage(Page[TraceOut]):
    total_capped: bool = False


class Facets(ApiModel):
    models: list[str]
    agents: list[str]
    tools: list[str]
    prompts: list[str]
    tags: list[str]
    environments: list[str]


class ProjectRef(ApiModel):
    project_id: uuid.UUID
