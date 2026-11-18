"""The shipped price table."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from importlib import resources


@dataclass(frozen=True, slots=True)
class BuiltinPrice:
    model: str
    provider: str
    pattern: str
    input_per_mtok: Decimal
    output_per_mtok: Decimal
    cached_input_per_mtok: Decimal | None


def load_builtin_prices() -> tuple[str, list[BuiltinPrice]]:
    """The table version and its rows."""
    document = json.loads(resources.files(__package__).joinpath("prices.json").read_text("utf-8"))

    def money(value: float | None) -> Decimal | None:
        return None if value is None else Decimal(str(value))

    rows = [
        BuiltinPrice(
            model=row["model"],
            provider=row["provider"],
            pattern=row["pattern"],
            input_per_mtok=Decimal(str(row["input_per_mtok"])),
            output_per_mtok=Decimal(str(row["output_per_mtok"])),
            cached_input_per_mtok=money(row["cached_input_per_mtok"]),
        )
        for row in document["prices"]
    ]
    return str(document["version"]), rows
