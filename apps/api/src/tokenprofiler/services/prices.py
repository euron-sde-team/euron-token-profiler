"""The price table: the shared builtin rows and per-project overrides."""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tokenprofiler.core.errors import ConflictError, NotFoundError
from tokenprofiler.ingest.pricing import PriceBook, normalize_model
from tokenprofiler.models import ModelPrice
from tokenprofiler.models.enums import PriceSource
from tokenprofiler.pricing import load_builtin_prices
from tokenprofiler.repositories.prices import PriceRepository
from tokenprofiler.schemas.prices import PriceOut, PriceWrite
from tokenprofiler.services import audit
from tokenprofiler.services.container import Container
from tokenprofiler.services.pricebook import entry_of
from tokenprofiler.services.principal import Principal


def default_pattern(model: str) -> str:
    return "^" + re.escape(normalize_model(model)).replace("\\-", "-") + "$"


def price_out(row: ModelPrice, rows: list[ModelPrice]) -> PriceOut:
    overridden = row.project_id is None and any(
        r.model == row.model and r.project_id is not None for r in rows
    )
    return PriceOut(
        id=row.id,
        model=row.model,
        match_pattern=row.match_pattern,
        provider=row.provider,
        input_per_mtok=row.input_per_mtok,
        output_per_mtok=row.output_per_mtok,
        cached_input_per_mtok=row.cached_input_per_mtok,
        source=row.source,
        scope="project" if row.project_id else "shared",
        overridden=overridden,
        updated_at=row.updated_at,
    )


class PriceService:
    def __init__(self, container: Container, session: AsyncSession) -> None:
        self.c = container
        self.session = session
        self.prices = PriceRepository(session)

    async def table(self, project_id: uuid.UUID) -> list[PriceOut]:
        rows = await self.prices.for_project(project_id)
        return [price_out(row, rows) for row in rows]

    async def upsert_override(
        self, principal: Principal, project_id: uuid.UUID, body: PriceWrite
    ) -> ModelPrice:
        existing = await self.prices.override_for(project_id, body.model)
        pattern = body.match_pattern or default_pattern(body.model)
        if existing is None:
            try:
                row = await self.prices.add(
                    ModelPrice(
                        project_id=project_id,
                        model=body.model,
                        match_pattern=pattern,
                        provider=body.provider,
                        input_per_mtok=body.input_per_mtok,
                        output_per_mtok=body.output_per_mtok,
                        cached_input_per_mtok=body.cached_input_per_mtok,
                        source=PriceSource.CUSTOM.value,
                    )
                )
            except IntegrityError as exc:
                await self.session.rollback()
                raise ConflictError("That model already has an override.") from exc
            action = "price.created"
        else:
            row = existing
            row.match_pattern = pattern
            row.provider = body.provider
            row.input_per_mtok = body.input_per_mtok
            row.output_per_mtok = body.output_per_mtok
            row.cached_input_per_mtok = body.cached_input_per_mtok
            action = "price.updated"
        details: dict[str, Any] = {
            "model": row.model,
            "input_per_mtok": float(row.input_per_mtok),
            "output_per_mtok": float(row.output_per_mtok),
        }
        await audit.record(
            self.session,
            principal=principal,
            project_id=project_id,
            action=action,
            target_type="price",
            target_id=row.id,
            details=details,
        )
        await self.session.commit()
        await self.session.refresh(row)
        self.c.prices.invalidate(project_id)
        return row

    async def delete_override(
        self, principal: Principal, project_id: uuid.UUID, price_id: uuid.UUID
    ) -> None:
        row = await self.prices.get(project_id, price_id)
        if row is None:
            raise NotFoundError("Override not found.")
        await self.prices.delete(row)
        await audit.record(
            self.session,
            principal=principal,
            project_id=project_id,
            action="price.deleted",
            target_type="price",
            target_id=price_id,
            details={"model": row.model},
        )
        await self.session.commit()
        self.c.prices.invalidate(project_id)

    async def lookup(self, project_id: uuid.UUID, model: str) -> PriceOut | None:
        """Which row would price a model name for this project (the "why this cost" check)."""
        rows = await self.prices.for_project(project_id)
        book = PriceBook(entry_of(row) for row in rows)
        entry = book.lookup(model)
        if entry is None:
            return None
        row = next(
            r
            for r in rows
            if r.model == entry.model and (r.project_id is not None) == entry.project_scoped
        )
        return price_out(row, rows)


async def sync_builtin_prices(container: Container) -> int:
    """Load the shipped table at startup (idempotent; edited rows are never overwritten)."""
    _, rows = load_builtin_prices()
    async with container.db.session() as session:
        count = await PriceRepository(session).sync_builtin(rows)
        await session.commit()
    container.prices.invalidate()
    return count
