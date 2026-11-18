"""Who is calling the control plane: a signed-in person (cookie or session token)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from tokenprofiler.core.security import SessionClaims
from tokenprofiler.models import User
from tokenprofiler.models.enums import Role


@dataclass(frozen=True, slots=True)
class Principal:
    user: User | None = None
    session: SessionClaims | None = None
    via_cookie: bool = False

    @property
    def user_id(self) -> uuid.UUID | None:
        return self.user.id if self.user is not None else None

    @property
    def is_admin(self) -> bool:
        return self.user is not None and self.user.role == Role.ADMIN

    @property
    def can_write(self) -> bool:
        return self.user is not None and Role(self.user.role).can_write
