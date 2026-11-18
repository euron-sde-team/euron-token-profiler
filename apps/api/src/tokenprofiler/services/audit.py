from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from tokenprofiler.models import AuditEvent
from tokenprofiler.repositories.audit import AuditRepository
from tokenprofiler.services.principal import Principal


async def record(
    session: AsyncSession,
    *,
    principal: Principal | None,
    project_id: uuid.UUID | None = None,
    action: str,
    target_type: str,
    target_id: object | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Add an audit event to the caller's transaction (it commits with the change it records)."""
    await AuditRepository(session).add(
        AuditEvent(
            actor_user_id=principal.user.id if principal and principal.user else None,
            project_id=project_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=details or {},
        )
    )
