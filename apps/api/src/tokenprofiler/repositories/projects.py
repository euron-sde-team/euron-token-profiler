from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select

from tokenprofiler.models import Project, Trace
from tokenprofiler.repositories.base import Repository


class ProjectRepository(Repository):
    async def get(self, project_id: uuid.UUID) -> Project | None:
        return await self.session.get(Project, project_id)

    async def by_slug(self, slug: str) -> Project | None:
        result = await self.session.execute(select(Project).where(Project.slug == slug))
        return result.scalar_one_or_none()

    async def all(self) -> list[Project]:
        result = await self.session.execute(select(Project).order_by(Project.created_at))
        return list(result.scalars())

    async def page(self, *, limit: int, offset: int, since: datetime) -> list[tuple[Project, int]]:
        """Projects (oldest first, so the default is stable) with their recent trace counts."""
        recent = (
            select(Trace.project_id, func.count().label("n"))
            .where(Trace.started_at >= since)
            .group_by(Trace.project_id)
            .subquery()
        )
        result = await self.session.execute(
            select(Project, func.coalesce(recent.c.n, 0))
            .outerjoin(recent, recent.c.project_id == Project.id)
            .order_by(Project.created_at, Project.id)
            .limit(limit)
            .offset(offset)
        )
        return [(project, int(count)) for project, count in result]

    async def count(self) -> int:
        return int(await self.session.scalar(select(func.count()).select_from(Project)) or 0)

    async def add(self, project: Project) -> Project:
        self.session.add(project)
        await self.session.flush()
        return project

    async def delete(self, project_id: uuid.UUID) -> None:
        await self.session.execute(delete(Project).where(Project.id == project_id))
