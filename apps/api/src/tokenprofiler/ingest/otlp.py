"""OpenTelemetry (OTLP/HTTP) ingest: JSON and protobuf bodies become the shared shape.

Attribute names follow the OpenTelemetry GenAI semantic conventions (`gen_ai.*`), with the
common instrumentation libraries' variants accepted too: OpenInference (`llm.*`,
`openinference.span.kind`), Traceloop (`traceloop.span.kind`) and the TokenProfiler
attributes (`tokenprofiler.*`) for what no convention covers: prompt name and version,
agent and tool names, a reported cost.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from tokenprofiler.ingest.types import Batch, SpanIn

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_HEX = re.compile(r"^[0-9a-fA-F]+$")
_ZERO_ID = re.compile(r"^0+$")

_OPERATION_KINDS = {
    "chat": "generation",
    "text_completion": "generation",
    "generate_content": "generation",
    "completion": "generation",
    "embeddings": "embedding",
    "embedding": "embedding",
    "execute_tool": "tool",
    "invoke_agent": "agent",
    "create_agent": "agent",
}
_SPAN_KINDS = {
    "llm": "generation",
    "embedding": "embedding",
    "tool": "tool",
    "agent": "agent",
    "retriever": "retriever",
    "generation": "generation",
    "span": "span",
}
_STATUS_ERROR = 2


def any_value(value: dict[str, Any]) -> Any:
    """Decode an OTLP AnyValue (`{"stringValue": "x"}` and friends) to plain Python."""
    if "stringValue" in value:
        return value["stringValue"]
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "boolValue" in value:
        return bool(value["boolValue"])
    if "arrayValue" in value:
        return [any_value(item) for item in value["arrayValue"].get("values", [])]
    if "kvlistValue" in value:
        return {
            item["key"]: any_value(item.get("value", {}))
            for item in value["kvlistValue"].get("values", [])
        }
    if "bytesValue" in value:
        return str(value["bytesValue"])
    return None


def attributes(items: list[dict[str, Any]] | None) -> dict[str, Any]:
    return {item["key"]: any_value(item.get("value", {})) for item in items or [] if "key" in item}


def _nanos(value: Any) -> datetime | None:
    try:
        return _EPOCH + timedelta(microseconds=int(value) // 1000)
    except (TypeError, ValueError, OverflowError):
        return None


def _span_id(value: Any, *, base64_ids: bool) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    text: str = value
    if base64_ids:
        try:
            text = base64.b64decode(value, validate=True).hex()
        except (binascii.Error, ValueError):
            return None
    if not _HEX.match(text) or _ZERO_ID.match(text):
        return None
    return text.lower()


def _first(attrs: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = attrs.get(name)
        if value is not None and value != "":
            return value
    return None


def _str(value: Any) -> str | None:
    return None if value is None else str(value)[:128]


def _int(value: Any) -> int | None:
    try:
        return None if value is None else max(0, int(float(value)))
    except (TypeError, ValueError):
        return None


def _money(value: Any) -> Decimal | None:
    try:
        return None if value is None else max(Decimal(0), Decimal(str(value)))
    except InvalidOperation:
        return None


def _jsonish(value: Any) -> Any:
    """Instrumentation libraries often send JSON documents as strings; keep them structured."""
    if isinstance(value, str) and value[:1] in "[{":
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _kind(attrs: dict[str, Any], has_usage: bool, has_model: bool) -> str:
    explicit = _first(attrs, "tokenprofiler.span.kind", "openinference.span.kind")
    if isinstance(explicit, str) and explicit.lower() in _SPAN_KINDS:
        return _SPAN_KINDS[explicit.lower()]
    operation = _first(attrs, "gen_ai.operation.name", "llm.request.type")
    if isinstance(operation, str) and operation.lower() in _OPERATION_KINDS:
        return _OPERATION_KINDS[operation.lower()]
    traceloop = _first(attrs, "traceloop.span.kind")
    if traceloop in {"tool", "agent"}:
        return str(traceloop)
    if has_model and has_usage:
        return "generation"
    return "span"


_METADATA_PREFIXES = ("metadata.", "tokenprofiler.metadata.", "langfuse.observation.metadata.")


def _span(raw: dict[str, Any], resource: dict[str, Any], *, base64_ids: bool) -> SpanIn | str:
    trace_id = _span_id(raw.get("traceId"), base64_ids=base64_ids)
    span_id = _span_id(raw.get("spanId"), base64_ids=base64_ids)
    started = _nanos(raw.get("startTimeUnixNano"))
    ended = _nanos(raw.get("endTimeUnixNano")) or started
    if trace_id is None or span_id is None or started is None or ended is None:
        return f"span {raw.get('name', '?')}: missing trace id, span id or start time"
    attrs = attributes(raw.get("attributes"))
    parent = _span_id(raw.get("parentSpanId"), base64_ids=base64_ids)

    model = _first(
        attrs, "gen_ai.response.model", "gen_ai.request.model", "llm.model_name", "ai.model.id"
    )
    input_tokens = _int(
        _first(
            attrs,
            "gen_ai.usage.input_tokens",
            "gen_ai.usage.prompt_tokens",
            "llm.token_count.prompt",
            "ai.usage.promptTokens",
        )
    )
    output_tokens = _int(
        _first(
            attrs,
            "gen_ai.usage.output_tokens",
            "gen_ai.usage.completion_tokens",
            "llm.token_count.completion",
            "ai.usage.completionTokens",
        )
    )
    cached = _int(
        _first(
            attrs,
            "gen_ai.usage.cache_read_input_tokens",
            "gen_ai.usage.cached_input_tokens",
            "llm.token_count.prompt_details.cache_read",
        )
    )
    kind = _kind(attrs, input_tokens is not None or output_tokens is not None, model is not None)

    status = raw.get("status") or {}
    errored = _int(status.get("code")) == _STATUS_ERROR or "error.type" in attrs
    message = status.get("message") or attrs.get("error.type")
    for event in raw.get("events") or []:
        if event.get("name") == "exception":
            event_attrs = attributes(event.get("attributes"))
            errored = True
            message = (
                message or event_attrs.get("exception.message") or event_attrs.get("exception.type")
            )

    service = resource.get("service.name")
    metadata: dict[str, Any] = {"service": service} if service else {}
    for key, value in attrs.items():
        for prefix in _METADATA_PREFIXES:
            if key.startswith(prefix):
                metadata[key.removeprefix(prefix)] = value

    parameters = {
        name: attrs[key]
        for name, key in (
            ("temperature", "gen_ai.request.temperature"),
            ("max_tokens", "gen_ai.request.max_tokens"),
            ("top_p", "gen_ai.request.top_p"),
        )
        if key in attrs
    }
    tags = _first(attrs, "tokenprofiler.trace.tags", "langfuse.trace.tags")
    version = _int(_first(attrs, "tokenprofiler.prompt.version"))
    prompt_name = _first(attrs, "tokenprofiler.prompt.name")
    ttft = _int(_first(attrs, "tokenprofiler.time_to_first_token_ms"))
    return SpanIn(
        trace_id=trace_id,
        span_id=span_id,
        parent_id=parent,
        name=str(raw.get("name") or "span")[:200],
        kind=kind,
        started_at=started,
        ended_at=max(ended, started),
        status="error" if errored else "ok",
        status_message=str(message)[:2000] if message else None,
        model=str(model)[:160] if model else None,
        provider=_str(
            _first(attrs, "gen_ai.provider.name", "gen_ai.system", "llm.provider", "llm.system")
        ),
        model_parameters=parameters,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached,
        reported_cost=_money(_first(attrs, "tokenprofiler.cost.total", "gen_ai.usage.cost")),
        reported_input_cost=_money(attrs.get("tokenprofiler.cost.input")),
        reported_output_cost=_money(attrs.get("tokenprofiler.cost.output")),
        time_to_first_token_ms=ttft,
        agent_name=_first(attrs, "gen_ai.agent.name", "tokenprofiler.agent.name"),
        tool_name=_first(attrs, "gen_ai.tool.name", "tokenprofiler.tool.name"),
        prompt_name=str(prompt_name) if prompt_name else None,
        prompt_version=version if prompt_name else None,
        input=_jsonish(
            _first(
                attrs,
                "tokenprofiler.input",
                "gen_ai.input.messages",
                "gen_ai.prompt",
                "input.value",
                "gen_ai.tool.call.arguments",
            )
        ),
        output=_jsonish(
            _first(
                attrs,
                "tokenprofiler.output",
                "gen_ai.output.messages",
                "gen_ai.completion",
                "output.value",
                "gen_ai.tool.call.result",
            )
        ),
        metadata=metadata,
        trace_name=str(raw["name"])[:200] if parent is None and raw.get("name") else None,
        user_id=_str(
            _first(attrs, "user.id", "enduser.id", "langfuse.user.id", "tokenprofiler.user.id")
        ),
        session_id=_str(
            _first(
                attrs,
                "session.id",
                "gen_ai.conversation.id",
                "langfuse.session.id",
                "tokenprofiler.session.id",
            )
        ),
        environment=_str(
            _first(
                {**resource, **attrs},
                "tokenprofiler.environment",
                "deployment.environment.name",
                "deployment.environment",
            )
        ),
        release=_str(resource.get("service.version")),
        tags=[str(tag)[:48] for tag in tags][:30] if isinstance(tags, list) else [],
    )


def parse_otlp(document: dict[str, Any], *, base64_ids: bool = False) -> Batch:
    batch = Batch()
    for resource_spans in document.get("resourceSpans") or []:
        resource = attributes((resource_spans.get("resource") or {}).get("attributes"))
        for scope_spans in resource_spans.get("scopeSpans") or []:
            for raw in scope_spans.get("spans") or []:
                result = _span(raw, resource, base64_ids=base64_ids)
                if isinstance(result, str):
                    if len(batch.rejected) < 20:
                        batch.rejected.append(result)
                else:
                    batch.spans.append(result)
    return batch
