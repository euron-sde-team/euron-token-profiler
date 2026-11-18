from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from tokenprofiler.db.base import Base, IdMixin

PRICE = Numeric(14, 6)


class ModelPrice(IdMixin, Base):
    """USD per million tokens for a model. A row with no project is the shared table; a row
    with a project overrides it for that project only (negotiated rates, self-hosted GPUs)."""

    __tablename__ = "model_prices"

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    model: Mapped[str] = mapped_column(String(120))
    # Regular expression over the normalised model name; the first lines of a model family
    # match its dated snapshots too.
    match_pattern: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(48), default="")
    input_per_mtok: Mapped[Decimal] = mapped_column(PRICE)
    output_per_mtok: Mapped[Decimal] = mapped_column(PRICE)
    cached_input_per_mtok: Mapped[Decimal | None] = mapped_column(PRICE)
    source: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
