"""Projects: create, configure (sampling, redaction, retention, webhook) and delete."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tokenprofiler.core.errors import ConflictError, NotFoundError, UnprocessableError
from tokenprofiler.models import Project
from tokenprofiler.repositories.projects import ProjectRepository
from tokenprofiler.schemas.projects import ProjectOut, ProjectUpdate
from tokenprofiler.schemas.redaction import RedactionRules
from tokenprofiler.services import audit
from tokenprofiler.services.container import Container
from tokenprofiler.services.principal import Principal
from tokenprofiler.services.webhooks import validate_webhook_url

RECENT = timedelta(days=7)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
    return slug or "project"


def project_out(project: Project, traces_7d: int = 0) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        name=project.name,
        slug=project.slug,
        description=project.description,
        sampling_rate=project.sampling_rate,
        keep_errors=project.keep_errors,
        keep_slow_ms=project.keep_slow_ms,
        redaction=RedactionRules.model_validate(project.redaction or {}),
        retention_days=project.retention_days,
        archive_before_delete=project.archive_before_delete,
        has_webhook=project.webhook_url_sealed is not None,
        created_at=project.created_at,
        traces_7d=traces_7d,
    )


class ProjectService:
    def __init__(self, container: Container, session: AsyncSession) -> None:
        self.c = container
        self.session = session
        self.projects = ProjectRepository(session)

    async def get(self, project_id: uuid.UUID) -> Project:
        project = await self.projects.get(project_id)
        if project is None:
            raise NotFoundError("Project not found.")
        return project

    async def page(self, *, limit: int, offset: int) -> list[ProjectOut]:
        rows = await self.projects.page(
            limit=limit, offset=offset, since=datetime.now(UTC) - RECENT
        )
        return [project_out(project, count) for project, count in rows]

    async def create(
        self, principal: Principal, *, name: str, description: str, slug: str | None = None
    ) -> Project:
        base = slug or slugify(name)
        for attempt in range(5):
            candidate = base if attempt == 0 else f"{base}-{uuid.uuid4().hex[:4]}"
            if await self.projects.by_slug(candidate) is not None:
                continue
            try:
                project = await self.projects.add(
                    Project(
                        name=name.strip(),
                        slug=candidate,
                        description=description,
                        retention_days=self.c.settings.default_retention_days,
                        redaction=RedactionRules().model_dump(mode="json"),
                        created_by=principal.user_id,
                    )
                )
            except IntegrityError:
                await self.session.rollback()
                continue
            await audit.record(
                self.session,
                principal=principal,
                project_id=project.id,
                action="project.created",
                target_type="project",
                target_id=project.id,
                details={"name": project.name},
            )
            await self.session.commit()
            return project
        raise ConflictError("Could not find a free project slug; pick another name.")

    async def update(
        self, principal: Principal, project_id: uuid.UUID, body: ProjectUpdate
    ) -> Project:
        project = await self.get(project_id)
        changes: dict[str, Any] = {}
        if body.name is not None and body.name != project.name:
            project.name = changes["name"] = body.name
        if body.description is not None and body.description != project.description:
            project.description = changes["description"] = body.description
        if body.sampling_rate is not None and body.sampling_rate != project.sampling_rate:
            project.sampling_rate = body.sampling_rate
            changes["sampling_rate"] = float(body.sampling_rate)
        if body.keep_errors is not None and body.keep_errors != project.keep_errors:
            project.keep_errors = changes["keep_errors"] = body.keep_errors
        if body.clear_keep_slow and project.keep_slow_ms is not None:
            project.keep_slow_ms = None
            changes["keep_slow_ms"] = None
        elif body.keep_slow_ms is not None and body.keep_slow_ms != project.keep_slow_ms:
            project.keep_slow_ms = changes["keep_slow_ms"] = body.keep_slow_ms
        if body.redaction is not None:
            stored = body.redaction.model_dump(mode="json")
            if stored != project.redaction:
                project.redaction = stored
                changes["redaction"] = {
                    "detectors": stored["detectors"],
                    "custom_rules": len(stored["custom"]),
                    "store_payloads": stored["store_payloads"],
                }
        if body.retention_days is not None and body.retention_days != project.retention_days:
            project.retention_days = changes["retention_days"] = body.retention_days
        if (
            body.archive_before_delete is not None
            and body.archive_before_delete != project.archive_before_delete
        ):
            project.archive_before_delete = changes["archive_before_delete"] = (
                body.archive_before_delete
            )
        if body.webhook_url is not None:
            if body.webhook_url == "":
                project.webhook_url_sealed = None
                changes["webhook"] = "removed"
            else:
                await validate_webhook_url(body.webhook_url, self.c.settings)
                project.webhook_url_sealed = self.c.secretbox.seal(
                    body.webhook_url, context=f"project:{project.id}:webhook"
                )
                changes["webhook"] = "set"
        if changes:
            await audit.record(
                self.session,
                principal=principal,
                project_id=project.id,
                action="project.updated",
                target_type="project",
                target_id=project.id,
                details=changes,
            )
            await self.session.commit()
        return project

    async def delete(self, principal: Principal, project_id: uuid.UUID) -> None:
        project = await self.get(project_id)
        if await self.projects.count() <= 1:
            raise UnprocessableError("Keep at least one project.", code="last_project")
        await audit.record(
            self.session,
            principal=principal,
            action="project.deleted",
            target_type="project",
            target_id=project.id,
            details={"name": project.name, "slug": project.slug},
        )
        await self.projects.delete(project.id)
        await self.session.commit()
        self.c.prices.invalidate(project.id)

    def webhook_url(self, project: Project) -> str | None:
        if project.webhook_url_sealed is None:
            return None
        return self.c.secretbox.open(
            project.webhook_url_sealed, context=f"project:{project.id}:webhook"
        )
