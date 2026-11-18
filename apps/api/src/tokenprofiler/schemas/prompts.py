from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import Field, StringConstraints

from tokenprofiler.schemas.common import ApiModel

PromptName = Annotated[
    str, StringConstraints(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
]
Label = Annotated[
    str, StringConstraints(min_length=1, max_length=32, pattern=r"^[a-z0-9][a-z0-9_-]*$")
]


class PromptVersionCreate(ApiModel):
    name: PromptName
    template: str = Field(min_length=1, max_length=100_000)
    config: dict[str, Any] = Field(default_factory=dict)
    labels: list[Label] = Field(default_factory=list, max_length=10)
    commit_message: Annotated[str, StringConstraints(max_length=300)] | None = None


class LabelMove(ApiModel):
    label: Label
    version: int | None = Field(
        default=None, ge=1, description="Version to point the label at; null removes the label."
    )


class PromptUsage(ApiModel):
    calls: int = 0
    errors: int = 0
    error_rate: float = 0
    cost: Decimal = Decimal(0)
    input_tokens: int = 0
    output_tokens: int = 0
    avg_tokens: int = 0
    p50_ms: float = 0
    p95_ms: float = 0
    last_seen: datetime | None = None


class PromptVersionOut(ApiModel):
    version: int
    template: str | None
    config: dict[str, Any]
    labels: list[str]
    commit_message: str | None
    managed: bool
    created_at: datetime
    usage: PromptUsage


class PromptSummary(ApiModel):
    name: str
    latest_version: int
    versions: int
    labels: list[str]
    managed: bool
    usage: PromptUsage
    updated_at: datetime


class PromptDetail(ApiModel):
    name: str
    versions: list[PromptVersionOut]
    usage: PromptUsage


class PromptFetch(ApiModel):
    name: str
    version: int
    template: str
    config: dict[str, Any]
    labels: list[str]
