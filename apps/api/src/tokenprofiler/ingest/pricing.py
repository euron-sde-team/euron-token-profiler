"""Turn token usage into dollars with a table of per-million-token prices.

The table is the shared builtin list (`pricing/prices.json`, refreshed with each release)
plus overrides entered by people, globally or for one project. A project's override always
beats the shared row. Models match by regular expression over a normalised name, so dated
snapshots and provider prefixes (`openai/gpt-4o-2024-08-06`, `bedrock/anthropic.claude-...`)
price like their family.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

MILLION = Decimal(1_000_000)
_PRECISION = Decimal("0.00000001")


def normalize_model(name: str) -> str:
    """Lowercase, drop the provider or routing prefix and any `:tag` after the name."""
    value = name.strip().lower()
    if "/" in value:
        value = value.rsplit("/", 1)[1]
    if value.startswith("anthropic."):
        value = value.removeprefix("anthropic.")
    # Bedrock revisions such as `-v2:0`; Ollama tags such as `llama3.2:3b` are kept.
    return re.sub(r"-v\d+(:\d+)?$", "", value)


@dataclass(frozen=True, slots=True)
class PriceEntry:
    model: str
    pattern: re.Pattern[str]
    input_per_mtok: Decimal
    output_per_mtok: Decimal
    cached_input_per_mtok: Decimal | None = None
    provider: str = ""
    project_scoped: bool = False


@dataclass(frozen=True, slots=True)
class Cost:
    input: Decimal
    output: Decimal

    @property
    def total(self) -> Decimal:
        return self.input + self.output


def compile_pattern(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


class PriceBook:
    def __init__(self, entries: Iterable[PriceEntry]) -> None:
        # Project overrides first, then the longest model name: `gpt-4o-mini` must be tried
        # before `gpt-4o` so a shorter family never swallows a more specific one.
        self.entries = sorted(entries, key=lambda e: (not e.project_scoped, -len(e.model)))
        self._memo: dict[str, PriceEntry | None] = {}

    def lookup(self, model: str) -> PriceEntry | None:
        if model in self._memo:
            return self._memo[model]
        name = normalize_model(model)
        found = next((e for e in self.entries if e.pattern.search(name)), None)
        if len(self._memo) < 4096:
            self._memo[model] = found
        return found

    def cost(
        self, model: str, *, input_tokens: int, output_tokens: int, cached_tokens: int = 0
    ) -> Cost | None:
        entry = self.lookup(model)
        if entry is None:
            return None
        cached = min(max(cached_tokens, 0), max(input_tokens, 0))
        fresh = max(input_tokens, 0) - cached
        cached_rate = (
            entry.cached_input_per_mtok
            if entry.cached_input_per_mtok is not None
            else entry.input_per_mtok
        )
        input_cost = (
            Decimal(fresh) * entry.input_per_mtok + Decimal(cached) * cached_rate
        ) / MILLION
        output_cost = Decimal(max(output_tokens, 0)) * entry.output_per_mtok / MILLION
        return Cost(input=input_cost.quantize(_PRECISION), output=output_cost.quantize(_PRECISION))
