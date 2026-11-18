"""Project API keys: created by people, used by SDKs and OpenTelemetry exporters to ingest."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from tokenprofiler.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from tokenprofiler.core.security import generate_api_key, parse_api_key, verify_api_key_secret
from tokenprofiler.models import ApiKey, Project
from tokenprofiler.repositories.api_keys import ApiKeyRepository
from tokenprofiler.repositories.projects import ProjectRepository
from tokenprofiler.services import audit
from tokenprofiler.services.container import Container
from tokenprofiler.services.principal import Principal

_TOUCH_INTERVAL_S = 60


class ApiKeyService:
    def __init__(self, container: Container, session: AsyncSession) -> None:
        self.c = container
        self.session = session
        self.keys = ApiKeyRepository(session)

    @property
    def _pepper(self) -> str:
        return self.c.settings.api_key_pepper.get_secret_value()

    async def create(
        self, principal: Principal, project_id: uuid.UUID, *, name: str
    ) -> tuple[ApiKey, str]:
        if principal.user is None:
            raise ForbiddenError("Keys are created by a signed-in person.")
        generated = generate_api_key(self._pepper)
        key = await self.keys.add(
            ApiKey(
                project_id=project_id,
                created_by=principal.user.id,
                name=name.strip(),
                prefix=generated.prefix,
                secret_hash=generated.secret_hash,
            )
        )
        await audit.record(
            self.session,
            principal=principal,
            project_id=project_id,
            action="api_key.created",
            target_type="api_key",
            target_id=key.id,
            details={"name": key.name, "prefix": key.prefix},
        )
        await self.session.commit()
        return key, generated.plaintext

    async def page(
        self, project_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[tuple[ApiKey, str | None]], int]:
        return await self.keys.page(project_id, limit=limit, offset=offset)

    async def revoke(
        self, principal: Principal, project_id: uuid.UUID, key_id: uuid.UUID
    ) -> ApiKey:
        key = await self.keys.get(project_id, key_id)
        if key is None:
            raise NotFoundError("API key not found.")
        if key.revoked_at is None:
            key.revoked_at = datetime.now(UTC)
            await audit.record(
                self.session,
                principal=principal,
                project_id=project_id,
                action="api_key.revoked",
                target_type="api_key",
                target_id=key.id,
                details={"name": key.name, "prefix": key.prefix},
            )
            await self.session.commit()
        return key

    async def resolve(self, raw: str) -> tuple[ApiKey, Project]:
        """The key and its project for an ingest request, or 401."""
        invalid = UnauthorizedError("That API key is not valid.", code="invalid_api_key")
        parsed = parse_api_key(raw)
        if parsed is None:
            raise invalid
        prefix, secret = parsed
        key = await self.keys.by_prefix(prefix)
        if key is None or not verify_api_key_secret(secret, key.secret_hash, self._pepper):
            raise invalid
        if key.revoked_at is not None:
            raise UnauthorizedError("That API key has been revoked.", code="invalid_api_key")
        project = await ProjectRepository(self.session).get(key.project_id)
        if project is None:
            raise invalid
        # Record use at most once a minute per key, so busy keys do not write on every call.
        if await self.c.redis.set(f"apikey:touched:{key.id}", b"1", ex=_TOUCH_INTERVAL_S, nx=True):
            key.last_used_at = datetime.now(UTC)
            await self.session.commit()
        return key, project
