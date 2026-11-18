"""People: administrators manage people and projects, members edit, viewers read."""

from __future__ import annotations

import uuid

import anyio
from sqlalchemy.ext.asyncio import AsyncSession

from tokenprofiler.core.config import Settings
from tokenprofiler.core.errors import ConflictError, NotFoundError, UnprocessableError
from tokenprofiler.core.security import hash_password, validate_password
from tokenprofiler.models import User
from tokenprofiler.models.enums import Role
from tokenprofiler.repositories.users import UserRepository
from tokenprofiler.services import audit
from tokenprofiler.services.auth import temporary_password
from tokenprofiler.services.container import Container, build_container
from tokenprofiler.services.principal import Principal


class UserService:
    def __init__(self, container: Container, session: AsyncSession) -> None:
        self.c = container
        self.session = session
        self.users = UserRepository(session)

    async def page(self, *, limit: int, offset: int) -> tuple[list[User], int]:
        return await self.users.page(limit=limit, offset=offset)

    async def create(
        self,
        principal: Principal,
        *,
        email: str,
        name: str,
        role: str,
        password: str | None = None,
    ) -> tuple[User, str]:
        if await self.users.by_email(email):
            raise ConflictError("An account with that email already exists.")
        secret = password or temporary_password()
        validate_password(secret, email=email)
        user = await self.users.add(
            User(
                email=email.strip().lower(),
                name=name.strip(),
                role=Role(role),
                password_hash=await anyio.to_thread.run_sync(hash_password, secret),
            )
        )
        await audit.record(
            self.session,
            principal=principal,
            action="user.created",
            target_type="user",
            target_id=user.id,
            details={"email": user.email, "role": user.role},
        )
        await self.session.commit()
        return user, secret

    async def update(
        self,
        principal: Principal,
        user_id: uuid.UUID,
        *,
        name: str | None,
        role: str | None,
        is_active: bool | None,
    ) -> User:
        user = await self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        demoting = (role is not None and role != Role.ADMIN) or is_active is False
        if demoting and user.role == Role.ADMIN and await self.users.count_admins() <= 1:
            raise UnprocessableError("Keep at least one active administrator.", code="last_admin")
        changes: dict[str, object] = {}
        if name is not None and name.strip() != user.name:
            user.name = name.strip()
            changes["name"] = user.name
        if role is not None and role != user.role:
            user.role = Role(role)
            changes["role"] = role
        if is_active is not None and is_active != user.is_active:
            user.is_active = is_active
            changes["is_active"] = is_active
        if "role" in changes or "is_active" in changes:
            # Role changes and deactivation take effect on the very next request.
            user.session_version += 1
        if changes:
            await audit.record(
                self.session,
                principal=principal,
                action="user.updated",
                target_type="user",
                target_id=user.id,
                details=changes,
            )
            await self.session.commit()
        return user


async def create_user_cli(
    settings: Settings, *, email: str, name: str, role: str, password: str | None
) -> tuple[User, str]:
    """Create a person from the operator CLI, with no browser session involved."""
    container = await build_container(settings)
    try:
        async with container.db.session() as session:
            return await UserService(container, session).create(
                Principal(), email=email, name=name, role=role, password=password
            )
    finally:
        await container.close()
