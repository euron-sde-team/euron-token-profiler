from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator

from tokenprofiler.ingest.redaction import validate_pattern
from tokenprofiler.schemas.common import ApiModel

Money = Annotated[Decimal, Field(ge=0, le=100_000, max_digits=14, decimal_places=6)]


class PriceWrite(ApiModel):
    model: Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]
    match_pattern: str | None = Field(
        default=None,
        max_length=200,
        description="Regular expression over the normalised model name (default: exact).",
    )
    provider: Annotated[str, StringConstraints(max_length=48)] = ""
    input_per_mtok: Money
    output_per_mtok: Money
    cached_input_per_mtok: Money | None = None

    @model_validator(mode="after")
    def _pattern(self) -> Self:
        if self.match_pattern and (problem := validate_pattern(self.match_pattern)):
            raise ValueError(problem)
        return self


class PriceOut(ApiModel):
    id: uuid.UUID
    model: str
    match_pattern: str
    provider: str
    input_per_mtok: Decimal
    output_per_mtok: Decimal
    cached_input_per_mtok: Decimal | None
    source: str
    scope: str = Field(description="shared or project")
    overridden: bool = Field(default=False, description="A project override hides this row.")
    updated_at: datetime
