from __future__ import annotations

import uuid

from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert

from tokenprofiler.models import ModelPrice
from tokenprofiler.models.enums import PriceSource
from tokenprofiler.pricing import BuiltinPrice
from tokenprofiler.repositories.base import Repository


class PriceRepository(Repository):
    async def for_project(self, project_id: uuid.UUID) -> list[ModelPrice]:
        """The shared table and this project's overrides."""
        result = await self.session.execute(
            select(ModelPrice)
            .where(or_(ModelPrice.project_id.is_(None), ModelPrice.project_id == project_id))
            .order_by(ModelPrice.provider, ModelPrice.model)
        )
        return list(result.scalars())

    async def get(self, project_id: uuid.UUID, price_id: uuid.UUID) -> ModelPrice | None:
        result = await self.session.execute(
            select(ModelPrice).where(ModelPrice.id == price_id, ModelPrice.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def override_for(self, project_id: uuid.UUID, model: str) -> ModelPrice | None:
        result = await self.session.execute(
            select(ModelPrice).where(ModelPrice.project_id == project_id, ModelPrice.model == model)
        )
        return result.scalar_one_or_none()

    async def add(self, price: ModelPrice) -> ModelPrice:
        self.session.add(price)
        await self.session.flush()
        return price

    async def delete(self, price: ModelPrice) -> None:
        await self.session.execute(delete(ModelPrice).where(ModelPrice.id == price.id))

    async def sync_builtin(self, rows: list[BuiltinPrice]) -> int:
        """Insert or refresh the shipped table. Rows people edited (custom) are left alone."""
        statement = insert(ModelPrice).values(
            [
                {
                    "id": uuid.uuid4(),
                    "project_id": None,
                    "model": row.model,
                    "match_pattern": row.pattern,
                    "provider": row.provider,
                    "input_per_mtok": row.input_per_mtok,
                    "output_per_mtok": row.output_per_mtok,
                    "cached_input_per_mtok": row.cached_input_per_mtok,
                    "source": PriceSource.BUILTIN.value,
                }
                for row in rows
            ]
        )
        new = statement.excluded
        await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[ModelPrice.model],
                index_where=ModelPrice.project_id.is_(None),
                set_={
                    "match_pattern": new.match_pattern,
                    "provider": new.provider,
                    "input_per_mtok": new.input_per_mtok,
                    "output_per_mtok": new.output_per_mtok,
                    "cached_input_per_mtok": new.cached_input_per_mtok,
                },
                where=ModelPrice.source == PriceSource.BUILTIN.value,
            )
        )
        return len(rows)
