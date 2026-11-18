"""Managed prompts: fetched by name, cached, filled in with variables."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_VARIABLE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}")


class PromptVariableError(KeyError):
    """A `{{variable}}` in the template had no value."""


@dataclass(frozen=True)
class Prompt:
    name: str
    version: int
    template: str
    config: dict[str, Any] = field(default_factory=dict)
    labels: tuple[str, ...] = ()

    @property
    def ref(self) -> tuple[str, int]:
        """What a generation records so usage and cost are attributed to this version."""
        return (self.name, self.version)

    @property
    def variables(self) -> list[str]:
        return list(dict.fromkeys(_VARIABLE.findall(self.template)))

    def compile(self, **values: object) -> str:
        """The template with every `{{variable}}` replaced. Extra values are ignored."""

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in values:
                raise PromptVariableError(
                    f"prompt {self.name!r} version {self.version} needs a value for {name!r}"
                )
            return str(values[name])

        return _VARIABLE.sub(replace, self.template)
