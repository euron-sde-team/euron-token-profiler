from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from tokenprofiler.db.base import Base, IdMixin, TimestampMixin


class Budget(IdMixin, TimestampMixin, Base):
    """A spend limit for a period, optionally narrowed to one model, agent, tool or prompt."""

    __tablename__ = "budgets"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    scope: Mapped[str] = mapped_column(String(16))
    scope_value: Mapped[str | None] = mapped_column(String(160))
    period: Mapped[str] = mapped_column(String(8))
    limit_usd: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    warn_at_percent: Mapped[int] = mapped_column(Integer, default=80)
    enabled: Mapped[bool] = mapped_column(default=True)


class AlertRule(IdMixin, TimestampMixin, Base):
    """A health check over a trailing window, for example p95 latency above 8 seconds."""

    __tablename__ = "alert_rules"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    metric: Mapped[str] = mapped_column(String(24))
    comparator: Mapped[str] = mapped_column(String(8))
    threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    window_minutes: Mapped[int] = mapped_column(Integer)
    # Fewer traces than this in the window means "not enough data", never an alert (except
    # for trace_count, which exists to notice silence).
    min_traces: Mapped[int] = mapped_column(Integer, default=10)
    severity: Mapped[str] = mapped_column(String(8), default="warning")
    enabled: Mapped[bool] = mapped_column(default=True)


class AlertEvent(IdMixin, Base):
    """One firing of a budget or a rule, from the moment it opens until it resolves."""

    __tablename__ = "alert_events"
    __table_args__ = (
        # A budget or rule has at most one open event at a time.
        Index(
            "uq_alert_events_open_source",
            "source_id",
            unique=True,
            postgresql_where=text("state = 'firing'"),
        ),
        Index("ix_alert_events_project_fired", "project_id", text("fired_at DESC")),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(8))
    source_id: Mapped[uuid.UUID]
    source_name: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(8))
    state: Mapped[str] = mapped_column(String(8))
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    message: Mapped[str] = mapped_column(Text)
    fired_at: Mapped[datetime] = mapped_column(server_default=func.now())
    resolved_at: Mapped[datetime | None]
    notified_at: Mapped[datetime | None]
    notify_error: Mapped[str | None] = mapped_column(String(200))
