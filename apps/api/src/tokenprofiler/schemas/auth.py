from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field

from tokenprofiler.schemas.common import ApiModel


class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class SetupRequest(ApiModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class PasswordChange(ApiModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class ProfileUpdate(ApiModel):
    name: str = Field(min_length=1, max_length=120)


class UserOut(ApiModel):
    id: uuid.UUID
    email: str
    name: str
    role: Literal["admin", "member", "viewer"]
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class SessionOut(ApiModel):
    user: UserOut
    token: str = Field(description="Also set as an httpOnly cookie for the web app.")
    expires_at: datetime


class UserCreate(ApiModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    role: Literal["admin", "member", "viewer"] = "member"


class UserCreated(ApiModel):
    user: UserOut
    temporary_password: str = Field(description="Shown once; share it with the person privately.")


class UserUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Literal["admin", "member", "viewer"] | None = None
    is_active: bool | None = None
