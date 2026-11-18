from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from tokenprofiler.db.base import Base, IdMixin, TimestampMixin


class Project(IdMixin, TimestampMixin, Base):
    """The unit of isolation: traces, prompts, prices, budgets and keys all belong to one."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(48), unique=True)
    description: Mapped[str] = mapped_column(String(300), default="")

    # Sampling: the fraction of traces kept (chosen by trace id, so a trace is never half
    # kept), with errors and slow spans always kept on top of it.
    sampling_rate: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal(1))
    keep_errors: Mapped[bool] = mapped_column(Boolean, default=True)
    keep_slow_ms: Mapped[int | None] = mapped_column(Integer)

    # PII redaction and payload storage rules, validated by schemas.redaction.RedactionRules.
    redaction: Mapped[dict[str, Any]] = mapped_column(
        default=dict, server_default=text("'{}'::jsonb")
    )

    retention_days: Mapped[int] = mapped_column(Integer, default=30)
    archive_before_delete: Mapped[bool] = mapped_column(Boolean, default=False)

    # Alert webhook, sealed with the secret box: URLs often carry a token.
    webhook_url_sealed: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
