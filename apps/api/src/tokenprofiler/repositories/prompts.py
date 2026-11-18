from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from tokenprofiler.models import PromptVersion
from tokenprofiler.repositories.base import Repository


class PromptRepository(Repository):
    async def latest_per_name(
        self, project_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[tuple[PromptVersion, int]], int]:
        """The newest version of each prompt with its version count, by name."""
        counts = (
            select(PromptVersion.name, func.count().label("n"))
            .where(PromptVersion.project_id == project_id)
            .group_by(PromptVersion.name)
            .subquery()
        )
        latest = (
            select(PromptVersion)
            .where(PromptVersion.project_id == project_id)
            .distinct(PromptVersion.name)
            .order_by(PromptVersion.name, PromptVersion.version.desc())
            .subquery()
        )
        total = await self.session.scalar(select(func.count()).select_from(counts))
        result = await self.session.execute(
            select(PromptVersion, counts.c.n)
            .join(latest, latest.c.id == PromptVersion.id)
            .join(counts, counts.c.name == PromptVersion.name)
            .order_by(PromptVersion.name)
            .limit(limit)
            .offset(offset)
        )
        return [(row[0], int(row[1])) for row in result], int(total or 0)

    async def versions(self, project_id: uuid.UUID, name: str) -> list[PromptVersion]:
        result = await self.session.execute(
            select(PromptVersion)
            .where(PromptVersion.project_id == project_id, PromptVersion.name == name)
            .order_by(PromptVersion.version.desc())
        )
        return list(result.scalars())

    async def get(self, project_id: uuid.UUID, name: str, version: int) -> PromptVersion | None:
        result = await self.session.execute(
            select(PromptVersion).where(
                PromptVersion.project_id == project_id,
                PromptVersion.name == name,
                PromptVersion.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def by_label(self, project_id: uuid.UUID, name: str, label: str) -> PromptVersion | None:
        result = await self.session.execute(
            select(PromptVersion)
            .where(
                PromptVersion.project_id == project_id,
                PromptVersion.name == name,
                PromptVersion.labels.contains([label]),
            )
            .order_by(PromptVersion.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def newest(self, project_id: uuid.UUID, name: str) -> PromptVersion | None:
        result = await self.session.execute(
            select(PromptVersion)
            .where(PromptVersion.project_id == project_id, PromptVersion.name == name)
            .order_by(PromptVersion.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def next_version(self, project_id: uuid.UUID, name: str) -> int:
        current = await self.session.scalar(
            select(func.max(PromptVersion.version)).where(
                PromptVersion.project_id == project_id, PromptVersion.name == name
            )
        )
        return int(current or 0) + 1

    async def add(self, version: PromptVersion) -> PromptVersion:
        self.session.add(version)
        await self.session.flush()
        return version

    async def register_seen(self, project_id: uuid.UUID, seen: set[tuple[str, int]]) -> None:
        """Record prompt versions first met in traces, so their usage has a home."""
        if not seen:
            return
        statement = insert(PromptVersion).values(
            [
                {
                    "id": uuid.uuid4(),
                    "project_id": project_id,
                    "name": name,
                    "version": version,
                    "managed": False,
                    "labels": [],
                    "config": {},
                }
                for name, version in sorted(seen)
            ]
        )
        await self.session.execute(
            statement.on_conflict_do_nothing(
                index_elements=[
                    PromptVersion.project_id,
                    PromptVersion.name,
                    PromptVersion.version,
                ]
            )
        )

    async def move_label(
        self, project_id: uuid.UUID, name: str, label: str, to_version: int | None
    ) -> None:
        """A label points at one version of a prompt at a time."""
        await self.session.execute(
            update(PromptVersion)
            .where(
                PromptVersion.project_id == project_id,
                PromptVersion.name == name,
                PromptVersion.labels.contains([label]),
            )
            .values(labels=func.array_remove(PromptVersion.labels, label))
        )
        if to_version is not None:
            await self.session.execute(
                update(PromptVersion)
                .where(
                    PromptVersion.project_id == project_id,
                    PromptVersion.name == name,
                    PromptVersion.version == to_version,
                )
                .values(labels=func.array_append(PromptVersion.labels, label))
            )
