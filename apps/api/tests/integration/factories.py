"""Builders for ingest payloads in the native protocol."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any


def trace_id() -> str:
    return uuid.uuid4().hex


def span(
    trace: str,
    name: str = "call",
    *,
    kind: str = "span",
    span_id: str | None = None,
    parent: str | None = None,
    started: datetime | None = None,
    duration_ms: int = 500,
    **fields: Any,
) -> dict[str, Any]:
    start = started or datetime.now(UTC) - timedelta(minutes=5)
    return {
        "id": span_id or uuid.uuid4().hex[:16],
        "trace_id": trace,
        "parent_id": parent,
        "name": name,
        "kind": kind,
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(milliseconds=duration_ms)).isoformat(),
        **fields,
    }


def generation(
    trace: str,
    *,
    model: str = "gpt-4o",
    input_tokens: int = 1000,
    output_tokens: int = 100,
    parent: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    return span(
        trace,
        "llm",
        kind="generation",
        parent=parent,
        model=model,
        usage={"input": input_tokens, "output": output_tokens},
        **fields,
    )
