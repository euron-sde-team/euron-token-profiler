"""People (administrators only)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from tokenprofiler.api.deps import AdminDep, ContainerDep, SessionDep
from tokenprofiler.schemas.auth import UserCreate, UserCreated, UserOut, UserUpdate
from tokenprofiler.schemas.common import Page
from tokenprofiler.services.users import UserService

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("", summary="Everyone with an account")
async def list_users(
    _: AdminDep,
    container: ContainerDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[UserOut]:
    users, total = await UserService(container, session).page(limit=limit, offset=offset)
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in users], total=total, limit=limit, offset=offset
    )


@router.post(
    "", summary="Create an account with a temporary password", status_code=status.HTTP_201_CREATED
)
async def create_user(
    body: UserCreate, principal: AdminDep, container: ContainerDep, session: SessionDep
) -> UserCreated:
    user, password = await UserService(container, session).create(
        principal, email=body.email, name=body.name, role=body.role
    )
    return UserCreated(user=UserOut.model_validate(user), temporary_password=password)


@router.patch("/{user_id}", summary="Rename, change the role, or deactivate")
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    principal: AdminDep,
    container: ContainerDep,
    session: SessionDep,
) -> UserOut:
    user = await UserService(container, session).update(
        principal, user_id, name=body.name, role=body.role, is_active=body.is_active
    )
    return UserOut.model_validate(user)
