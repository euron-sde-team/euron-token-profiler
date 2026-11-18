from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, ForeignKeyConstraint, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from tokenprofiler.db.base import Base

COST = Numeric(18, 8)


class Trace(Base):
    """One request through an application. Totals are denormalised from its spans at
    ingest, so the dashboards and the list never aggregate spans on the hot path."""

    __tablename__ = "traces"

    project_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    user_id: Mapped[str | None] = mapped_column(String(128))
    session_id: Mapped[str | None] = mapped_column(String(128))
    environment: Mapped[str] = mapped_column(String(48), default="default")
    release: Mapped[str | None] = mapped_column(String(64))
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    started_at: Mapped[datetime]
    ended_at: Mapped[datetime]
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(8), default="ok")
    input: Mapped[str | None] = mapped_column(Text)
    output: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", default=dict, server_default=text("'{}'::jsonb")
    )

    span_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    generation_count: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    total_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    total_cost: Mapped[Decimal] = mapped_column(COST, default=Decimal(0))
    models: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    agents: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    tools: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    prompts: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)


class Span(Base):
    """One step: a model call, a tool call, an agent run or any other unit of work."""

    __tablename__ = "spans"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "trace_id"],
            ["traces.project_id", "traces.id"],
            ondelete="CASCADE",
            name="fk_spans_trace",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(16), default="span")
    started_at: Mapped[datetime]
    ended_at: Mapped[datetime]
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    time_to_first_token_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(8), default="ok")
    status_message: Mapped[str | None] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(8), default="default")

    # Attribution: the nearest agent and tool above (or at) this span.
    agent_name: Mapped[str | None] = mapped_column(String(120))
    tool_name: Mapped[str | None] = mapped_column(String(120))
    prompt_name: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[int | None] = mapped_column(Integer)

    model: Mapped[str | None] = mapped_column(String(160))
    provider: Mapped[str | None] = mapped_column(String(48))
    model_parameters: Mapped[dict[str, Any]] = mapped_column(
        default=dict, server_default=text("'{}'::jsonb")
    )
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cached_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    total_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    usage_estimated: Mapped[bool] = mapped_column(default=False)
    input_cost: Mapped[Decimal] = mapped_column(COST, default=Decimal(0))
    output_cost: Mapped[Decimal] = mapped_column(COST, default=Decimal(0))
    total_cost: Mapped[Decimal] = mapped_column(COST, default=Decimal(0))
    cost_source: Mapped[str | None] = mapped_column(String(16))  # reported | table | none

    input: Mapped[str | None] = mapped_column(Text)
    output: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", default=dict, server_default=text("'{}'::jsonb")
    )
    redactions: Mapped[int] = mapped_column(Integer, default=0)
