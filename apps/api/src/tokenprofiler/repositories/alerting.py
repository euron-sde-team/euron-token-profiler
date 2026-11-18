from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select

from tokenprofiler.models import AlertEvent, AlertRule, Budget, Project
from tokenprofiler.repositories.base import Repository


class AlertRepository(Repository):
    async def budgets(self, project_id: uuid.UUID) -> list[Budget]:
        result = await self.session.execute(
            select(Budget).where(Budget.project_id == project_id).order_by(Budget.created_at)
        )
        return list(result.scalars())

    async def budget(self, project_id: uuid.UUID, budget_id: uuid.UUID) -> Budget | None:
        result = await self.session.execute(
            select(Budget).where(Budget.id == budget_id, Budget.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def rules(self, project_id: uuid.UUID) -> list[AlertRule]:
        result = await self.session.execute(
            select(AlertRule)
            .where(AlertRule.project_id == project_id)
            .order_by(AlertRule.created_at)
        )
        return list(result.scalars())

    async def rule(self, project_id: uuid.UUID, rule_id: uuid.UUID) -> AlertRule | None:
        result = await self.session.execute(
            select(AlertRule).where(AlertRule.id == rule_id, AlertRule.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def add(self, row: Budget | AlertRule | AlertEvent) -> None:
        self.session.add(row)
        await self.session.flush()

    async def delete_budget(self, budget: Budget) -> None:
        await self.session.execute(delete(Budget).where(Budget.id == budget.id))
        await self.session.execute(delete(AlertEvent).where(AlertEvent.source_id == budget.id))

    async def delete_rule(self, rule: AlertRule) -> None:
        await self.session.execute(delete(AlertRule).where(AlertRule.id == rule.id))
        await self.session.execute(delete(AlertEvent).where(AlertEvent.source_id == rule.id))

    async def open_event(self, source_id: uuid.UUID) -> AlertEvent | None:
        result = await self.session.execute(
            select(AlertEvent).where(
                AlertEvent.source_id == source_id, AlertEvent.state == "firing"
            )
        )
        return result.scalar_one_or_none()

    async def events(
        self, project_id: uuid.UUID, *, limit: int, offset: int, firing_only: bool
    ) -> tuple[list[AlertEvent], int]:
        conditions = [AlertEvent.project_id == project_id]
        if firing_only:
            conditions.append(AlertEvent.state == "firing")
        total = await self.session.scalar(
            select(func.count()).select_from(AlertEvent).where(*conditions)
        )
        result = await self.session.execute(
            select(AlertEvent)
            .where(*conditions)
            .order_by(AlertEvent.fired_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars()), int(total or 0)

    async def firing_count(self, project_id: uuid.UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(AlertEvent)
                .where(AlertEvent.project_id == project_id, AlertEvent.state == "firing")
            )
            or 0
        )

    async def projects_with_alerting(self) -> list[Project]:
        """Projects that have at least one enabled budget or rule."""
        budgeted = select(Budget.project_id).where(Budget.enabled.is_(True))
        ruled = select(AlertRule.project_id).where(AlertRule.enabled.is_(True))
        result = await self.session.execute(
            select(Project).where(Project.id.in_(budgeted.union(ruled)))
        )
        return list(result.scalars())

    async def purge_resolved(self, before: datetime) -> int:
        result = await self.session.execute(
            delete(AlertEvent).where(
                AlertEvent.state == "resolved", AlertEvent.resolved_at < before
            )
        )
        return int(result.rowcount or 0)  # type: ignore[attr-defined]
