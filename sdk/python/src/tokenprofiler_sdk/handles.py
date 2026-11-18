"""Spans and traces as context managers that nest through `contextvars`."""

from __future__ import annotations

import contextvars
import secrets
import traceback
from datetime import datetime, timezone
from types import TracebackType
from typing import TYPE_CHECKING, Any

from tokenprofiler_sdk.prompts import Prompt

if TYPE_CHECKING:
    from tokenprofiler_sdk.client import TokenProfiler

_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("tp_trace_id", default=None)
_span_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("tp_span_id", default=None)
_agent: contextvars.ContextVar[str | None] = contextvars.ContextVar("tp_agent", default=None)

KINDS = {"span", "generation", "embedding", "agent", "tool", "retriever"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_trace_id() -> str:
    return secrets.token_hex(16)


def new_span_id() -> str:
    return secrets.token_hex(8)


def current_trace_id() -> str | None:
    return _trace_id.get()


def current_span_id() -> str | None:
    return _span_id.get()


class Span:
    """One step. Use as `with profiler.span("name") as span:`; call `update` as results arrive.

    An exception leaving the block marks the span failed (type and message are recorded) and
    is re-raised unchanged. Entering a span with no trace open starts one, so a bare
    `profiler.generation(...)` is already a complete trace.
    """

    def __init__(
        self,
        client: TokenProfiler,
        name: str,
        kind: str = "span",
        *,
        input: Any = None,
        output: Any = None,
        metadata: dict[str, Any] | None = None,
        model: str | None = None,
        provider: str | None = None,
        model_parameters: dict[str, Any] | None = None,
        usage: dict[str, int] | None = None,
        cost: dict[str, float] | None = None,
        prompt: Prompt | tuple[str, int] | None = None,
        agent: str | None = None,
        tool: str | None = None,
        level: str = "default",
    ) -> None:
        if kind not in KINDS:
            raise ValueError(f"unknown span kind {kind!r}; use one of {sorted(KINDS)}")
        self._client = client
        self.name = name
        self.kind = kind
        self.id = new_span_id()
        self.trace_id: str = ""
        self.parent_id: str | None = None
        self.fields: dict[str, Any] = {
            "input": input,
            "output": output,
            "metadata": dict(metadata or {}),
            "model": model,
            "provider": provider,
            "model_parameters": dict(model_parameters or {}),
            "usage": usage,
            "cost": cost,
            "agent": agent,
            "tool": tool,
            "level": level,
        }
        self.prompt = prompt
        self.status = "ok"
        self.status_message: str | None = None
        self.started_at = _now()
        self.first_token_at: datetime | None = None
        self._tokens: list[contextvars.Token[Any]] = []
        self._own_trace = False

    def update(self, **values: Any) -> Span:
        """Set or replace fields: output, usage, cost, metadata (merged), model, level, ..."""
        metadata = values.pop("metadata", None)
        if metadata:
            self.fields["metadata"].update(metadata)
        for key, value in values.items():
            if key == "prompt":
                self.prompt = value
            elif key in self.fields:
                self.fields[key] = value
            else:
                raise TypeError(f"unknown span field {key!r}")
        return self

    def mark_first_token(self) -> None:
        """Call when the first streamed token arrives; time to first token is recorded."""
        if self.first_token_at is None:
            self.first_token_at = _now()

    def fail(self, message: str) -> None:
        self.status = "error"
        self.status_message = message[:2000]

    def start(self) -> Span:
        trace = _trace_id.get()
        if trace is None:
            trace = new_trace_id()
            self._own_trace = True
            self._tokens.append(_trace_id.set(trace))
        self.trace_id = trace
        self.parent_id = _span_id.get()
        self._tokens.append(_span_id.set(self.id))
        if self.kind == "agent" and not self.fields["agent"]:
            self._tokens.append(_agent.set(self.name))
        self.started_at = _now()
        return self

    def end(self) -> None:
        for token in reversed(self._tokens):
            token.var.reset(token)
        self._tokens.clear()
        self._client._emit_span(self)
        if self._own_trace:
            self._client._emit_trace(self.trace_id, name=self.name)

    def __enter__(self) -> Span:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc is not None:
            detail = "".join(traceback.format_exception_only(exc_type, exc)).strip()
            self.fail(detail)
        self.end()

    def to_payload(self) -> dict[str, Any]:
        ended = _now()
        body: dict[str, Any] = {
            "id": self.id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "kind": self.kind,
            "start_time": self.started_at.isoformat(),
            "end_time": ended.isoformat(),
            "status": self.status,
            "status_message": self.status_message,
            "level": "error" if self.status == "error" else self.fields["level"],
        }
        for key in ("model", "provider", "usage", "cost", "tool", "input", "output"):
            if self.fields[key] is not None:
                body[key] = self.fields[key]
        agent = self.fields["agent"] or (_agent.get() if self.kind != "agent" else None)
        if agent:
            body["agent"] = agent
        if self.fields["model_parameters"]:
            body["model_parameters"] = self.fields["model_parameters"]
        if self.fields["metadata"]:
            body["metadata"] = self.fields["metadata"]
        if self.first_token_at is not None:
            body["time_to_first_token_ms"] = int(
                (self.first_token_at - self.started_at).total_seconds() * 1000
            )
        if self.prompt is not None:
            name, version = self.prompt.ref if isinstance(self.prompt, Prompt) else self.prompt
            body["prompt"] = {"name": name, "version": version}
        return body


class Trace:
    """Trace-level fields (user, session, tags) around a group of spans."""

    def __init__(
        self,
        client: TokenProfiler,
        name: str,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        input: Any = None,
        trace_id: str | None = None,
    ) -> None:
        self._client = client
        self.id = trace_id or new_trace_id()
        self.fields: dict[str, Any] = {
            "name": name,
            "user_id": user_id,
            "session_id": session_id,
            "tags": list(tags or []),
            "metadata": dict(metadata or {}),
            "input": input,
            "output": None,
        }
        self._token: contextvars.Token[str | None] | None = None
        self._span_token: contextvars.Token[str | None] | None = None

    def update(self, **values: Any) -> Trace:
        for key, value in values.items():
            if key not in self.fields:
                raise TypeError(f"unknown trace field {key!r}")
            self.fields[key] = value
        return self

    def __enter__(self) -> Trace:
        self._token = _trace_id.set(self.id)
        self._span_token = _span_id.set(None)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._token is not None:
            _trace_id.reset(self._token)
        if self._span_token is not None:
            _span_id.reset(self._span_token)
        self._client._emit_trace(self.id, **self.fields)
