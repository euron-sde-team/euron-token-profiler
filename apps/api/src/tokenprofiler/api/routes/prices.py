"""The price table and per-project overrides."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from tokenprofiler.api.deps import ContainerDep, ProjectDep, SessionDep, WriterDep
from tokenprofiler.core.errors import NotFoundError
from tokenprofiler.schemas.prices import PriceOut, PriceWrite
from tokenprofiler.services.prices import PriceService, price_out

router = APIRouter(prefix="/api/v1/projects/{project_id}/prices", tags=["prices"])


@router.get("", summary="The shared price table and this project's overrides")
async def list_prices(
    project: ProjectDep, container: ContainerDep, session: SessionDep
) -> list[PriceOut]:
    return await PriceService(container, session).table(project.id)


@router.get("/lookup", summary="Which price applies to a model name")
async def lookup(
    project: ProjectDep,
    container: ContainerDep,
    session: SessionDep,
    model: Annotated[str, Query(min_length=1, max_length=160)],
) -> PriceOut:
    found = await PriceService(container, session).lookup(project.id, model)
    if found is None:
        raise NotFoundError("No price matches that model; its cost is recorded as zero.")
    return found


@router.put("", summary="Create or replace this project's override for a model")
async def put_override(
    body: PriceWrite,
    project: ProjectDep,
    principal: WriterDep,
    container: ContainerDep,
    session: SessionDep,
) -> PriceOut:
    service = PriceService(container, session)
    row = await service.upsert_override(principal, project.id, body)
    return price_out(row, [row])


@router.delete("/{price_id}", summary="Remove an override", status_code=status.HTTP_204_NO_CONTENT)
async def delete_override(
    price_id: uuid.UUID,
    project: ProjectDep,
    principal: WriterDep,
    container: ContainerDep,
    session: SessionDep,
) -> Response:
    await PriceService(container, session).delete_override(principal, project.id, price_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
