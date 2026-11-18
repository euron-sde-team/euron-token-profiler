"""Prompts: versions, labels and what each version costs in use."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from tokenprofiler.api.deps import ProjectDep, SessionDep, WriterDep
from tokenprofiler.schemas.common import Ok, Page
from tokenprofiler.schemas.prompts import (
    LabelMove,
    PromptDetail,
    PromptSummary,
    PromptUsage,
    PromptVersionCreate,
    PromptVersionOut,
)
from tokenprofiler.services.prompts import PromptService

router = APIRouter(prefix="/api/v1/projects/{project_id}/prompts", tags=["prompts"])


@router.get("", summary="Prompts with their newest version and usage")
async def list_prompts(
    project: ProjectDep,
    session: SessionDep,
    range: Annotated[str | None, Query(description="Usage window: 24h, 7d, 14d, 30d")] = "7d",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[PromptSummary]:
    items, total = await PromptService(session).page(
        project.id, range_key=range, limit=limit, offset=offset
    )
    return Page[PromptSummary](items=items, total=total, limit=limit, offset=offset)


@router.post("", summary="Save a new version of a prompt", status_code=201)
async def create_version(
    body: PromptVersionCreate, project: ProjectDep, principal: WriterDep, session: SessionDep
) -> PromptVersionOut:
    version = await PromptService(session).create_version(principal, project.id, body)
    return PromptVersionOut(
        version=version.version,
        template=version.template,
        config=version.config,
        labels=version.labels,
        commit_message=version.commit_message,
        managed=version.managed,
        created_at=version.created_at,
        usage=PromptUsage(),
    )


@router.put("/{name:path}/label", summary="Point a label at a version (or remove it)")
async def move_label(
    name: str, body: LabelMove, project: ProjectDep, principal: WriterDep, session: SessionDep
) -> Ok:
    await PromptService(session).move_label(principal, project.id, name, body)
    return Ok()


@router.get("/{name:path}", summary="Every version of a prompt with its usage")
async def get_prompt(
    name: str,
    project: ProjectDep,
    session: SessionDep,
    range: Annotated[str | None, Query(description="Usage window: 24h, 7d, 14d, 30d")] = "7d",
) -> PromptDetail:
    return await PromptService(session).detail(project.id, name, range)
