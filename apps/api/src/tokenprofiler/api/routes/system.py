"""Deployment info and the audit trail."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from tokenprofiler import __version__
from tokenprofiler.api.deps import AdminDep, ContainerDep, SessionDep
from tokenprofiler.repositories.audit import AuditRepository
from tokenprofiler.repositories.users import UserRepository
from tokenprofiler.schemas.common import Page
from tokenprofiler.schemas.system import AuditOut, SystemInfo

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/system/info", summary="Deployment capabilities (public)")
async def system_info(container: ContainerDep, session: SessionDep) -> SystemInfo:
    settings = container.settings
    return SystemInfo(
        product_name=settings.product_name,
        version=__version__,
        needs_setup=await UserRepository(session).count() == 0,
        allow_signup=settings.allow_signup,
        archive_store=settings.archive_store,
        default_retention_days=settings.default_retention_days,
        ingest_rate_limit=settings.ingest_rate_limit,
        dashboard_cache_ttl_s=settings.dashboard_cache_ttl_s,
        api_url=settings.api_url,
    )


@router.get("/audit", summary="Who changed what (administrators)")
async def audit_log(
    _: AdminDep,
    session: SessionDep,
    project_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AuditOut]:
    rows, total = await AuditRepository(session).page(
        limit=limit, offset=offset, project_id=project_id
    )
    items = [
        AuditOut(
            id=str(event.id),
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            project_id=event.project_id,
            details=event.details,
            actor_name=name,
            created_at=event.created_at,
        )
        for event, name in rows
    ]
    return Page[AuditOut](items=items, total=total, limit=limit, offset=offset)
