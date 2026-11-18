"""Prompts: immutable versions, movable labels, and what each version cost in use."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tokenprofiler.core.errors import ConflictError, NotFoundError
from tokenprofiler.models import PromptVersion
from tokenprofiler.repositories.metrics import BreakdownRow, MetricsRepository
from tokenprofiler.repositories.prompts import PromptRepository
from tokenprofiler.schemas.prompts import (
    LabelMove,
    PromptDetail,
    PromptFetch,
    PromptSummary,
    PromptUsage,
    PromptVersionCreate,
    PromptVersionOut,
)
from tokenprofiler.services import audit
from tokenprofiler.services.dashboards import resolve_window
from tokenprofiler.services.principal import Principal

PRODUCTION = "production"


def _usage(rows: list[BreakdownRow]) -> PromptUsage:
    if not rows:
        return PromptUsage()
    calls = sum(r.calls for r in rows)
    errors = sum(r.errors for r in rows)
    generations = sum(r.generations for r in rows)
    input_tokens = sum(r.input_tokens for r in rows)
    output_tokens = sum(r.output_tokens for r in rows)
    # Percentiles do not combine across versions; the busiest version's are the honest
    # single number for a prompt as a whole.
    busiest = max(rows, key=lambda r: r.calls)
    return PromptUsage(
        calls=calls,
        errors=errors,
        error_rate=round(100 * errors / calls, 2) if calls else 0.0,
        cost=sum((r.cost for r in rows), Decimal(0)),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        avg_tokens=round((input_tokens + output_tokens) / generations) if generations else 0,
        p50_ms=round(busiest.p50_ms),
        p95_ms=round(busiest.p95_ms),
        last_seen=max(r.last_seen for r in rows),
    )


class PromptService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.prompts = PromptRepository(session)
        self.metrics = MetricsRepository(session)

    async def _usage_rows(
        self, project_id: uuid.UUID, range_key: str | None
    ) -> dict[str, list[BreakdownRow]]:
        start, end = resolve_window(range_key or "7d", None, None, now=datetime.now(UTC))
        rows = await self.metrics.breakdown(project_id, "prompt", start, end, limit=1000)
        grouped: dict[str, list[BreakdownRow]] = defaultdict(list)
        for row in rows:
            grouped[row.key].append(row)
        return grouped

    async def page(
        self, project_id: uuid.UUID, *, range_key: str | None, limit: int, offset: int
    ) -> tuple[list[PromptSummary], int]:
        latest, total = await self.prompts.latest_per_name(project_id, limit=limit, offset=offset)
        usage = await self._usage_rows(project_id, range_key)
        return [
            PromptSummary(
                name=version.name,
                latest_version=version.version,
                versions=count,
                labels=version.labels,
                managed=version.managed,
                usage=_usage(usage.get(version.name, [])),
                updated_at=version.created_at,
            )
            for version, count in latest
        ], total

    async def detail(self, project_id: uuid.UUID, name: str, range_key: str | None) -> PromptDetail:
        versions = await self.prompts.versions(project_id, name)
        if not versions:
            raise NotFoundError("Prompt not found.")
        usage = await self._usage_rows(project_id, range_key)
        rows = usage.get(name, [])
        by_version = {row.version: row for row in rows}
        return PromptDetail(
            name=name,
            versions=[
                PromptVersionOut(
                    version=v.version,
                    template=v.template,
                    config=v.config,
                    labels=v.labels,
                    commit_message=v.commit_message,
                    managed=v.managed,
                    created_at=v.created_at,
                    usage=_usage([by_version[v.version]])
                    if v.version in by_version
                    else PromptUsage(),
                )
                for v in versions
            ],
            usage=_usage(rows),
        )

    async def create_version(
        self, principal: Principal, project_id: uuid.UUID, body: PromptVersionCreate
    ) -> PromptVersion:
        for _ in range(3):
            version = await self.prompts.next_version(project_id, body.name)
            try:
                created = await self.prompts.add(
                    PromptVersion(
                        project_id=project_id,
                        name=body.name,
                        version=version,
                        template=body.template,
                        config=body.config,
                        labels=[],
                        commit_message=body.commit_message,
                        managed=True,
                        created_by=principal.user_id,
                    )
                )
            except IntegrityError:
                # Another writer took this number; try the next one.
                await self.session.rollback()
                continue
            for label in dict.fromkeys(body.labels):
                await self.prompts.move_label(project_id, body.name, label, version)
            await audit.record(
                self.session,
                principal=principal,
                project_id=project_id,
                action="prompt.version_created",
                target_type="prompt",
                target_id=body.name,
                details={"version": version, "labels": body.labels},
            )
            await self.session.commit()
            await self.session.refresh(created)
            return created
        raise ConflictError("Two people saved this prompt at once; try again.")

    async def move_label(
        self, principal: Principal, project_id: uuid.UUID, name: str, body: LabelMove
    ) -> None:
        if (
            body.version is not None
            and await self.prompts.get(project_id, name, body.version) is None
        ):
            raise NotFoundError("Prompt version not found.")
        if not await self.prompts.versions(project_id, name):
            raise NotFoundError("Prompt not found.")
        await self.prompts.move_label(project_id, name, body.label, body.version)
        await audit.record(
            self.session,
            principal=principal,
            project_id=project_id,
            action="prompt.label_moved",
            target_type="prompt",
            target_id=name,
            details={"label": body.label, "version": body.version},
        )
        await self.session.commit()

    async def fetch(
        self, project_id: uuid.UUID, name: str, *, version: int | None, label: str | None
    ) -> PromptFetch:
        """What an SDK gets: a pinned version, a label, or production, else the newest."""
        if version is not None:
            found = await self.prompts.get(project_id, name, version)
        elif label is not None:
            found = await self.prompts.by_label(project_id, name, label)
        else:
            found = await self.prompts.by_label(project_id, name, PRODUCTION)
            found = found or await self.prompts.newest(project_id, name)
        if found is None or found.template is None:
            raise NotFoundError("No managed prompt matches that name, version or label.")
        return PromptFetch(
            name=found.name,
            version=found.version,
            template=found.template,
            config=found.config,
            labels=found.labels,
        )
