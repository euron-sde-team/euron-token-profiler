from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import Field, StringConstraints

from tokenprofiler.schemas.common import ApiModel
from tokenprofiler.schemas.redaction import RedactionRules

Name = Annotated[str, StringConstraints(min_length=1, max_length=80, strip_whitespace=True)]


class ProjectCreate(ApiModel):
    name: Name
    description: Annotated[str, StringConstraints(max_length=300)] = ""


class ProjectUpdate(ApiModel):
    name: Name | None = None
    description: Annotated[str, StringConstraints(max_length=300)] | None = None
    sampling_rate: Decimal | None = Field(default=None, ge=0, le=1)
    keep_errors: bool | None = None
    keep_slow_ms: int | None = Field(default=None, ge=1, le=3_600_000)
    clear_keep_slow: bool = Field(default=False, description="Turn the slow-span override off.")
    redaction: RedactionRules | None = None
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    archive_before_delete: bool | None = None
    webhook_url: str | None = Field(
        default=None, max_length=500, description="Empty string removes the webhook."
    )


class ProjectOut(ApiModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str
    sampling_rate: Decimal
    keep_errors: bool
    keep_slow_ms: int | None
    redaction: RedactionRules
    retention_days: int
    archive_before_delete: bool
    has_webhook: bool
    created_at: datetime
    traces_7d: int = 0


class RedactionTest(ApiModel):
    text: str = Field(min_length=1, max_length=5000)
    redaction: RedactionRules | None = Field(
        default=None, description="Rules to try; the project's saved rules when omitted."
    )


class RedactionTestResult(ApiModel):
    redacted: str
    redactions: int
    by_rule: dict[str, int]


class ApiKeyCreate(ApiModel):
    name: Name


class ApiKeyOut(ApiModel):
    id: uuid.UUID
    name: str
    prefix: str
    created_by_name: str | None
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreated(ApiKeyOut):
    key: str = Field(description="The full key. Shown once; only a keyed hash is stored.")
