"""The project's redaction rules as stored (projects.redaction) and as edited in the UI."""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator

from tokenprofiler.ingest.redaction import (
    BUILTIN_DETECTORS,
    DEFAULT_DETECTORS,
    Redactor,
    build_redactor,
    validate_pattern,
)
from tokenprofiler.schemas.common import ApiModel


class CustomRule(ApiModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=40, strip_whitespace=True)]
    pattern: str = Field(min_length=1, max_length=200)
    replacement: Annotated[str, StringConstraints(max_length=60, pattern=r"^[^\"\\\n]*$")] = (
        "[REDACTED]"
    )

    @model_validator(mode="after")
    def _safe_pattern(self) -> Self:
        if problem := validate_pattern(self.pattern):
            raise ValueError(problem)
        return self


class RedactionRules(ApiModel):
    detectors: list[str] = Field(
        default_factory=lambda: list(DEFAULT_DETECTORS),
        description=f"Built-in detectors to apply: {', '.join(BUILTIN_DETECTORS)}.",
    )
    custom: list[CustomRule] = Field(default_factory=list, max_length=20)
    store_payloads: bool = Field(
        default=True, description="Off keeps no inputs or outputs, only the shape and the usage."
    )
    max_payload_chars: int = Field(default=20_000, ge=100, le=200_000)
    redact_metadata: bool = True

    @model_validator(mode="after")
    def _known_detectors(self) -> Self:
        unknown = sorted(set(self.detectors) - set(BUILTIN_DETECTORS))
        if unknown:
            raise ValueError(f"Unknown detectors: {', '.join(unknown)}.")
        self.detectors = list(dict.fromkeys(self.detectors))
        return self

    def redactor(self) -> Redactor:
        return build_redactor(
            detectors=self.detectors,
            custom=[(rule.name, rule.pattern, rule.replacement) for rule in self.custom],
            store_payloads=self.store_payloads,
            max_chars=self.max_payload_chars,
            redact_metadata=self.redact_metadata,
        )
