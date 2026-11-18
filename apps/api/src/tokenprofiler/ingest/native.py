"""The native protocol: validate each item on its own and convert it to the shared shape."""

from __future__ import annotations

from pydantic import ValidationError

from tokenprofiler.ingest.types import Batch, SpanIn, TraceIn
from tokenprofiler.schemas.ingest import IngestBatch, SpanPayload, TracePayload

MAX_REJECTION_NOTES = 20


def _why(index: int, label: str, exc: ValidationError) -> str:
    first = exc.errors()[0]
    where = ".".join(str(part) for part in first["loc"])
    return f"{label}[{index}] {where}: {first['msg']}"


def parse_native(batch: IngestBatch) -> Batch:
    parsed = Batch()
    for index, raw in enumerate(batch.spans):
        try:
            span = SpanPayload.model_validate(raw)
        except ValidationError as exc:
            parsed.rejected.append(_why(index, "spans", exc))
            continue
        usage, cost = span.usage, span.cost
        parsed.spans.append(
            SpanIn(
                trace_id=span.trace_id,
                span_id=span.id,
                parent_id=span.parent_id,
                name=span.name,
                kind=span.kind,
                started_at=span.start_time,
                ended_at=span.end_time or span.start_time,
                status=span.status,
                status_message=span.status_message,
                level=span.level,
                model=span.model,
                provider=span.provider,
                model_parameters=span.model_parameters,
                input_tokens=usage.input if usage else None,
                output_tokens=usage.output if usage else None,
                cached_tokens=usage.cached if usage else None,
                reported_cost=cost.total if cost else None,
                reported_input_cost=cost.input if cost else None,
                reported_output_cost=cost.output if cost else None,
                time_to_first_token_ms=span.time_to_first_token_ms,
                agent_name=span.agent,
                tool_name=span.tool,
                prompt_name=span.prompt.name if span.prompt else None,
                prompt_version=span.prompt.version if span.prompt else None,
                input=span.input,
                output=span.output,
                metadata=span.metadata,
            )
        )
    for index, raw in enumerate(batch.traces):
        try:
            trace = TracePayload.model_validate(raw)
        except ValidationError as exc:
            parsed.rejected.append(_why(index, "traces", exc))
            continue
        parsed.traces.append(
            TraceIn(
                trace_id=trace.id,
                name=trace.name,
                user_id=trace.user_id,
                session_id=trace.session_id,
                environment=trace.environment,
                release=trace.release,
                tags=list(dict.fromkeys(trace.tags)),
                metadata=trace.metadata,
                input=trace.input,
                output=trace.output,
                timestamp=trace.timestamp,
            )
        )
    del parsed.rejected[MAX_REJECTION_NOTES:]
    return parsed
