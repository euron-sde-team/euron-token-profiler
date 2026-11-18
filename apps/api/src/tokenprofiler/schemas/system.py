from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from tokenprofiler.schemas.common import ApiModel


class SystemInfo(ApiModel):
    product_name: str
    version: str
    needs_setup: bool
    allow_signup: bool
    archive_store: str
    default_retention_days: int
    ingest_rate_limit: int
    dashboard_cache_ttl_s: int
    api_url: str


class AuditOut(ApiModel):
    id: str
    action: str
    target_type: str
    target_id: str | None
    project_id: uuid.UUID | None
    details: dict[str, Any]
    actor_name: str | None
    created_at: datetime
