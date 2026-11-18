"""Request dependencies: infrastructure, the caller on each plane, roles, the project."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from tokenprofiler.core import metrics
from tokenprofiler.core.config import Settings
from tokenprofiler.core.errors import (
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    UnauthorizedError,
)
from tokenprofiler.core.security import looks_like_api_key
from tokenprofiler.models import ApiKey, Project, User
from tokenprofiler.models.enums import Role
from tokenprofiler.repositories.projects import ProjectRepository
from tokenprofiler.services.auth import SESSION_COOKIE, AuthService
from tokenprofiler.services.container import Container
from tokenprofiler.services.keys import ApiKeyService
from tokenprofiler.services.principal import Principal

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


async def get_session(container: ContainerDep) -> AsyncIterator[AsyncSession]:
    async with container.db.session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _origin_allowed(request: Request, settings: Settings) -> bool:
    """CSRF defence for cookie sessions: unsafe methods must come from our own web app."""
    origin = request.headers.get("origin")
    if origin is None and (referer := request.headers.get("referer")):
        parts = urlsplit(referer)
        origin = f"{parts.scheme}://{parts.netloc}"
    allowed = {*settings.cors_origins, settings.web_url.rstrip("/")}
    return origin in allowed


async def _session_principal(
    request: Request, container: Container, session: AsyncSession
) -> Principal | None:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if looks_like_api_key(token):
            return None
        user, claims = await AuthService(container, session).resolve(token)
        return Principal(user=user, session=claims)
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        user, claims = await AuthService(container, session).resolve(cookie)
        if request.method not in _SAFE_METHODS and not _origin_allowed(request, container.settings):
            raise ForbiddenError("Cross-site request blocked.", code="csrf")
        return Principal(user=user, session=claims, via_cookie=True)
    return None


async def get_principal(
    request: Request, container: ContainerDep, session: SessionDep
) -> Principal:
    """The control plane is for people: a session token or the session cookie."""
    principal = await _session_principal(request, container, session)
    if principal is None:
        if looks_like_api_key(request.headers.get("authorization", "")[7:].strip()):
            raise ForbiddenError(
                "Project API keys send traces (/v1/ingest). Sign in to use the dashboard API.",
                code="api_key_not_allowed",
            )
        raise UnauthorizedError()
    return principal


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def get_user(principal: PrincipalDep) -> User:
    if principal.user is None:
        raise UnauthorizedError()
    return principal.user


UserDep = Annotated[User, Depends(get_user)]


def require_admin(principal: PrincipalDep) -> Principal:
    if principal.user is None or principal.user.role != Role.ADMIN:
        raise ForbiddenError("This needs an administrator.")
    return principal


AdminDep = Annotated[Principal, Depends(require_admin)]


def require_writer(principal: PrincipalDep) -> Principal:
    if not principal.can_write:
        raise ForbiddenError("Your role is read only.")
    return principal


WriterDep = Annotated[Principal, Depends(require_writer)]


async def get_project(project_id: uuid.UUID, _: PrincipalDep, session: SessionDep) -> Project:
    project = await ProjectRepository(session).get(project_id)
    if project is None:
        raise NotFoundError("Project not found.")
    return project


ProjectDep = Annotated[Project, Depends(get_project)]


def _raw_key(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return request.headers.get("x-api-key", "").strip()


async def get_ingest_key(
    request: Request, response: Response, container: ContainerDep, session: SessionDep
) -> tuple[ApiKey, Project]:
    """The ingest plane: a project API key, then a per-key rate limit."""
    raw = _raw_key(request)
    if not raw:
        raise UnauthorizedError(
            "Send a project API key: Authorization: Bearer tp_... (or x-api-key).",
            code="invalid_api_key",
        )
    key, project = await ApiKeyService(container, session).resolve(raw)
    result = await container.limiter.hit(f"ingest:{key.id}", container.settings.ingest_rate_limit)
    response.headers.update(result.headers())
    if not result.allowed:
        metrics.RATE_LIMITED.labels("ingest").inc()
        raise RateLimitedError(
            "This key is sending too many requests. Batch more spans per request.",
            headers={"retry-after": str(result.reset_s), **result.headers()},
        )
    return key, project


IngestKeyDep = Annotated[tuple[ApiKey, Project], Depends(get_ingest_key)]
