"""Head sampling by trace id.

The decision is a pure function of the trace id and the rate, so every span of a trace (and
every batch it arrives in, from any SDK process) gets the same answer and a kept trace is
never half stored. Errors and slow spans override the rate (see `IngestService`).
"""

from __future__ import annotations

import hashlib
from decimal import Decimal


def sample_fraction(trace_id: str) -> float:
    digest = hashlib.sha256(trace_id.encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def keep_by_rate(trace_id: str, rate: Decimal | float) -> bool:
    rate = float(rate)
    if rate >= 1:
        return True
    if rate <= 0:
        return False
    return sample_fraction(trace_id) < rate
