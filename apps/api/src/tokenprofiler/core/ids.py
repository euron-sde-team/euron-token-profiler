"""Time-ordered UUIDs (RFC 9562 version 7).

Random v4 keys scatter inserts across the whole primary-key index; v7 keys arrive in
roughly increasing order, so hot B-tree pages stay in cache as the request log grows.
"""

from __future__ import annotations

import os
import secrets
import time
import uuid


def uuid7() -> uuid.UUID:
    unix_ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")
    value = (
        (unix_ms & 0xFFFF_FFFF_FFFF) << 80
        | 0x7 << 76
        | ((rand >> 64) & 0xFFF) << 64
        | 0b10 << 62
        | (rand & 0x3FFF_FFFF_FFFF_FFFF)
    )
    return uuid.UUID(int=value)


def short_id(prefix: str, length: int = 24) -> str:
    """Opaque public ids in OpenAI's style, for example `chatcmpl-5f1c...`."""
    return f"{prefix}-{secrets.token_hex(length // 2)}"
