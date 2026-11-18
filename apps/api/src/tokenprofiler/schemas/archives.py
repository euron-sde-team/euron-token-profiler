from __future__ import annotations

from tokenprofiler.schemas.common import ApiModel


class ArchiveObject(ApiModel):
    key: str
    size_bytes: int
