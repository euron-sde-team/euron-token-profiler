from __future__ import annotations

import uuid

from sqlalchemy import func, select

from tokenprofiler.models import ApiKey, User
from tokenprofiler.repositories.base import Repository


class ApiKeyRepository(Repository):
    async def by_prefix(self, prefix: str) -> ApiKey | None:
        result = await self.session.execute(select(ApiKey).where(ApiKey.prefix == prefix))
        return result.scalar_one_or_none()

    async def get(self, project_id: uuid.UUID, key_id: uuid.UUID) -> ApiKey | None:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def page(
        self, project_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[tuple[ApiKey, str | None]], int]:
        total = await self.session.scalar(
            select(func.count()).select_from(ApiKey).where(ApiKey.project_id == project_id)
        )
        result = await self.session.execute(
            select(ApiKey, User.name)
            .outerjoin(User, User.id == ApiKey.created_by)
            .where(ApiKey.project_id == project_id)
            .order_by(ApiKey.revoked_at.is_not(None), ApiKey.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [(key, name) for key, name in result], int(total or 0)

    async def add(self, key: ApiKey) -> ApiKey:
        self.session.add(key)
        await self.session.flush()
        return key
