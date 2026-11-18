"""Sign-in, sessions, first-run setup and passwords."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta

import anyio
from sqlalchemy.ext.asyncio import AsyncSession

from tokenprofiler.core.errors import (
    ConflictError,
    ForbiddenError,
    RateLimitedError,
    UnauthorizedError,
)
from tokenprofiler.core.security import (
    SessionClaims,
    decode_session,
    hash_password,
    issue_session,
    password_needs_rehash,
    validate_password,
    verify_password,
)
from tokenprofiler.models import User
from tokenprofiler.models.enums import Role
from tokenprofiler.repositories.users import UserRepository
from tokenprofiler.services.container import Container

SESSION_COOKIE = "tokenprofiler_session"
LOCKOUT_THRESHOLD = 8
LOCKOUT = timedelta(minutes=15)


def _revoked_key(jti: str) -> str:
    return f"session:revoked:{jti}"


class AuthService:
    def __init__(self, container: Container, session: AsyncSession) -> None:
        self.c = container
        self.session = session
        self.users = UserRepository(session)

    def _issue(self, user: User) -> tuple[str, SessionClaims]:
        return issue_session(
            user.id,
            user.session_version,
            secret=self.c.settings.session_secret.get_secret_value(),
            ttl=timedelta(hours=self.c.settings.session_ttl_hours),
        )

    async def login(self, email: str, password: str) -> tuple[User, str, SessionClaims]:
        user = await self.users.by_email(email)
        now = datetime.now(UTC)
        if user and user.locked_until and user.locked_until > now:
            minutes = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
            raise RateLimitedError(f"Too many failed sign-ins. Try again in {minutes} minute(s).")
        # Argon2 is deliberately slow; keep it off the event loop.
        valid = await anyio.to_thread.run_sync(
            verify_password, user.password_hash if user else None, password
        )
        if user is None or not valid or not user.is_active:
            if user is not None and not valid:
                user.failed_logins += 1
                if user.failed_logins >= LOCKOUT_THRESHOLD:
                    user.locked_until = now + LOCKOUT
                    user.failed_logins = 0
                await self.session.commit()
            raise UnauthorizedError("Email or password is incorrect.", code="invalid_credentials")
        if password_needs_rehash(user.password_hash):
            user.password_hash = await anyio.to_thread.run_sync(hash_password, password)
        user.failed_logins = 0
        user.locked_until = None
        user.last_login_at = now
        await self.session.commit()
        token, claims = self._issue(user)
        return user, token, claims

    async def resolve(self, token: str) -> tuple[User, SessionClaims]:
        claims = decode_session(token, secret=self.c.settings.session_secret.get_secret_value())
        if await self.c.redis.exists(_revoked_key(claims.jti)):
            raise UnauthorizedError("You have signed out. Sign in again.")
        user = await self.users.get(claims.user_id)
        if user is None or not user.is_active or user.session_version != claims.session_version:
            raise UnauthorizedError("Your session has ended. Sign in again.")
        return user, claims

    async def logout(self, claims: SessionClaims) -> None:
        ttl = int((claims.expires_at - datetime.now(UTC)).total_seconds())
        if ttl > 0:
            await self.c.redis.set(_revoked_key(claims.jti), b"1", ex=ttl)

    async def setup(self, email: str, name: str, password: str) -> User:
        """Create the first account (an administrator), or a member when sign-up is open."""
        first = await self.users.count() == 0
        if not first and not self.c.settings.allow_signup:
            raise ForbiddenError("Sign-up is closed. Ask an administrator to create your account.")
        validate_password(password, email=email)
        if await self.users.by_email(email):
            raise ConflictError("An account with that email already exists.")
        user = await self.users.add(
            User(
                email=email.strip().lower(),
                name=name.strip(),
                password_hash=await anyio.to_thread.run_sync(hash_password, password),
                role=Role.ADMIN if first else Role.MEMBER,
            )
        )
        await self.session.commit()
        return user

    async def change_password(
        self, user: User, current: str, new: str
    ) -> tuple[str, SessionClaims]:
        if not await anyio.to_thread.run_sync(verify_password, user.password_hash, current):
            raise UnauthorizedError(
                "Your current password is incorrect.", code="invalid_credentials"
            )
        validate_password(new, email=user.email)
        user.password_hash = await anyio.to_thread.run_sync(hash_password, new)
        # Every other session (other browsers, stolen cookies) ends now.
        user.session_version += 1
        await self.session.commit()
        return self._issue(user)

    async def update_profile(self, user: User, name: str) -> User:
        user.name = name.strip()
        await self.session.commit()
        return user


def temporary_password() -> str:
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    body = "".join(secrets.choice(alphabet) for _ in range(14))
    return f"{body[:7]}-{body[7:]}"


def is_valid_name(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9._:/-]{0,118}[a-z0-9])?", value))
