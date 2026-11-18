"""Projects, their settings (sampling, redaction, retention, webhook) and their keys."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from tokenprofiler.api.deps import (
    AdminDep,
    ContainerDep,
    PrincipalDep,
    ProjectDep,
    SessionDep,
    WriterDep,
)
from tokenprofiler.schemas.common import Page
from tokenprofiler.schemas.projects import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    RedactionTest,
    RedactionTestResult,
)
from tokenprofiler.schemas.redaction import RedactionRules
from tokenprofiler.services.keys import ApiKeyService
from tokenprofiler.services.projects import ProjectService, project_out

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("", summary="Projects, oldest first, with their recent trace counts")
async def list_projects(
    _: PrincipalDep,
    container: ContainerDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ProjectOut]:
    service = ProjectService(container, session)
    items = await service.page(limit=limit, offset=offset)
    total = await service.projects.count()
    return Page[ProjectOut](items=items, total=total, limit=limit, offset=offset)


@router.post("", summary="Create a project", status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate, principal: AdminDep, container: ContainerDep, session: SessionDep
) -> ProjectOut:
    project = await ProjectService(container, session).create(
        principal, name=body.name, description=body.description
    )
    return project_out(project)


@router.get("/{project_id}", summary="One project and its settings")
async def get_project(project: ProjectDep) -> ProjectOut:
    return project_out(project)


@router.patch("/{project_id}", summary="Change settings: sampling, redaction, retention, webhook")
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    principal: AdminDep,
    container: ContainerDep,
    session: SessionDep,
) -> ProjectOut:
    project = await ProjectService(container, session).update(principal, project_id, body)
    return project_out(project)


@router.delete(
    "/{project_id}",
    summary="Delete a project and everything in it",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project(
    project_id: uuid.UUID, principal: AdminDep, container: ContainerDep, session: SessionDep
) -> Response:
    await ProjectService(container, session).delete(principal, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/redaction/test", summary="Try redaction rules on sample text")
async def try_redaction(
    body: RedactionTest, project: ProjectDep, _: WriterDep
) -> RedactionTestResult:
    rules = body.redaction or RedactionRules.model_validate(project.redaction or {})
    redactor = rules.redactor()
    redacted = redactor.mask(body.text)
    return RedactionTestResult(
        redacted=redacted, redactions=redactor.count, by_rule=dict(redactor.hits)
    )


@router.get("/{project_id}/keys", summary="Project API keys")
async def list_keys(
    project: ProjectDep,
    container: ContainerDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ApiKeyOut]:
    rows, total = await ApiKeyService(container, session).page(
        project.id, limit=limit, offset=offset
    )
    items = [
        ApiKeyOut(
            id=key.id,
            name=key.name,
            prefix=key.prefix,
            created_by_name=name,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            revoked_at=key.revoked_at,
        )
        for key, name in rows
    ]
    return Page[ApiKeyOut](items=items, total=total, limit=limit, offset=offset)


@router.post("/{project_id}/keys", summary="Create a key (shown once)", status_code=201)
async def create_key(
    body: ApiKeyCreate,
    project: ProjectDep,
    principal: WriterDep,
    container: ContainerDep,
    session: SessionDep,
) -> ApiKeyCreated:
    key, plaintext = await ApiKeyService(container, session).create(
        principal, project.id, name=body.name
    )
    return ApiKeyCreated(
        id=key.id,
        name=key.name,
        prefix=key.prefix,
        created_by_name=principal.user.name if principal.user else None,
        created_at=key.created_at,
        last_used_at=None,
        revoked_at=None,
        key=plaintext,
    )


@router.delete("/{project_id}/keys/{key_id}", summary="Revoke a key")
async def revoke_key(
    key_id: uuid.UUID,
    project: ProjectDep,
    principal: WriterDep,
    container: ContainerDep,
    session: SessionDep,
) -> ApiKeyOut:
    key = await ApiKeyService(container, session).revoke(principal, project.id, key_id)
    return ApiKeyOut(
        id=key.id,
        name=key.name,
        prefix=key.prefix,
        created_by_name=None,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
        revoked_at=key.revoked_at,
    )
