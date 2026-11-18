from __future__ import annotations

import uuid

from sqlalchemy import func, select

from tokenprofiler.models import AuditEvent, User
from tokenprofiler.repositories.base import Repository


class AuditRepository(Repository):
    async def add(self, event: AuditEvent) -> None:
        self.session.add(event)
        await self.session.flush()

    async def page(
        self, *, limit: int, offset: int, project_id: uuid.UUID | None = None
    ) -> tuple[list[tuple[AuditEvent, str | None]], int]:
        conditions = [] if project_id is None else [AuditEvent.project_id == project_id]
        total = await self.session.scalar(
            select(func.count()).select_from(AuditEvent).where(*conditions)
        )
        result = await self.session.execute(
            select(AuditEvent, User.name)
            .outerjoin(User, User.id == AuditEvent.actor_user_id)
            .where(*conditions)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [(event, name) for event, name in result], int(total or 0)
