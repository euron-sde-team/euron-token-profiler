"""Archived traces: what retention wrote before it deleted them."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response

from tokenprofiler.api.deps import AdminDep, ContainerDep, ProjectDep
from tokenprofiler.core.errors import UnprocessableError
from tokenprofiler.schemas.archives import ArchiveObject

router = APIRouter(prefix="/api/v1/projects/{project_id}/archives", tags=["archives"])


@router.get("", summary="Archive objects for this project (administrators)")
async def list_archives(
    project: ProjectDep,
    _: AdminDep,
    container: ContainerDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ArchiveObject]:
    items = await container.archive.list(f"{project.slug}/", limit)
    return [ArchiveObject(key=key, size_bytes=size) for key, size in items]


@router.get("/download", summary="Download one archive object (gzip NDJSON)")
async def download(
    project: ProjectDep,
    _: AdminDep,
    container: ContainerDep,
    key: Annotated[str, Query(min_length=3, max_length=300)],
) -> Response:
    if not key.startswith(f"{project.slug}/"):
        raise UnprocessableError("That object belongs to another project.")
    try:
        data = await container.archive.get(key)
    except ValueError as exc:
        raise UnprocessableError("That is not a valid archive key.") from exc
    return Response(
        data,
        media_type="application/gzip",
        headers={"content-disposition": f'attachment; filename="{key.rsplit("/", 1)[-1]}"'},
    )
