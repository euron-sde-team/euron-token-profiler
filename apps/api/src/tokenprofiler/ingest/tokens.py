"""A cheap token estimate for spans whose provider reported no usage.

Real tokenisers are model specific and heavy. The estimate (about four ASCII characters per
token, one token per other character) is within roughly 15 percent for English and code and
is flagged `usage_estimated` on the span, so nobody mistakes it for a measured number.
"""

from __future__ import annotations

import json
from typing import Any


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def estimate_tokens(value: Any) -> int:
    text = _text(value)
    if not text:
        return 0
    ascii_chars = sum(1 for ch in text if ord(ch) < 128)
    other = len(text) - ascii_chars
    return max(1, round(ascii_chars / 4) + other)
