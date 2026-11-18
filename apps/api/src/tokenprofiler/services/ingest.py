"""The ingest pipeline: sample, price, redact and store a batch of traces and spans.

Order matters. Usage is estimated and cost computed from the original payloads (a redacted
or truncated prompt would estimate low); only then are payloads masked and cut to the
project's limits, so what reaches the database never holds what a rule removed. Everything
for one request commits in one transaction: attribution, the denormalised trace totals and
the prompt registry are always consistent with the spans beside them.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import String, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from tokenprofiler.core import metrics
from tokenprofiler.ingest.attribution import resolve_attribution
from tokenprofiler.ingest.pricing import PriceBook
from tokenprofiler.ingest.redaction import Redactor
from tokenprofiler.ingest.sampling import keep_by_rate
from tokenprofiler.ingest.tokens import estimate_tokens
from tokenprofiler.ingest.types import Batch, SpanIn, TraceIn
from tokenprofiler.models import Project
from tokenprofiler.repositories.prompts import PromptRepository
from tokenprofiler.repositories.traces import TraceRepository
from tokenprofiler.schemas.ingest import IngestResult
from tokenprofiler.schemas.redaction import RedactionRules
from tokenprofiler.services.container import Container

_METERED = {"generation", "embedding"}
_LOCK = text(
    "SELECT pg_advisory_xact_lock(k) FROM "
    "(SELECT hashtextextended(x, 0) AS k FROM unnest(:keys) AS x ORDER BY 1) AS s"
).bindparams(bindparam("keys", type_=ARRAY(String)))


def _clean(value: str | None, limit: int) -> str | None:
    return None if value is None else value.replace("\x00", "")[:limit]


def _millis(started: datetime, ended: datetime) -> int:
    return max(0, int((ended - started).total_seconds() * 1000))


@dataclass(slots=True)
class _Priced:
    input_tokens: int
    output_tokens: int
    estimated: bool
    input_cost: Decimal
    output_cost: Decimal
    source: str | None


def price_span(span: SpanIn, kind: str, book: PriceBook) -> _Priced:
    """Usage (estimated when missing) and cost (reported, from the table, or unknown)."""
    if kind not in _METERED:
        return _Priced(0, 0, False, Decimal(0), Decimal(0), None)
    estimated = False
    input_tokens, output_tokens = span.input_tokens, span.output_tokens
    if input_tokens is None:
        input_tokens = estimate_tokens(span.input)
        estimated = estimated or input_tokens > 0
    if output_tokens is None:
        output_tokens = 0 if kind == "embedding" else estimate_tokens(span.output)
        estimated = estimated or output_tokens > 0
    zero = Decimal(0)
    if (
        span.reported_cost is not None
        or span.reported_input_cost is not None
        or span.reported_output_cost is not None
    ):
        input_cost = span.reported_input_cost or zero
        total = span.reported_cost
        output_cost = span.reported_output_cost or zero
        if total is not None:
            output_cost = max(zero, total - input_cost)
        return _Priced(input_tokens, output_tokens, estimated, input_cost, output_cost, "reported")
    if span.model:
        cost = book.cost(
            span.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=span.cached_tokens or 0,
        )
        if cost is not None:
            return _Priced(input_tokens, output_tokens, estimated, cost.input, cost.output, "table")
    return _Priced(input_tokens, output_tokens, estimated, zero, zero, "none")


class IngestService:
    def __init__(self, container: Container, session: AsyncSession) -> None:
        self.c = container
        self.session = session
        self.traces = TraceRepository(session)

    def _decide(self, project: Project, spans_by_trace: dict[str, list[SpanIn]]) -> set[str]:
        kept: set[str] = set()
        for trace_id, spans in spans_by_trace.items():
            if (
                keep_by_rate(trace_id, project.sampling_rate)
                or (project.keep_errors and any(span.status == "error" for span in spans))
                or (
                    project.keep_slow_ms is not None
                    and any(
                        _millis(span.started_at, span.ended_at) >= project.keep_slow_ms
                        for span in spans
                    )
                )
            ):
                kept.add(trace_id)
        return kept

    def _span_row(
        self, project_id: uuid.UUID, span: SpanIn, redactor: Redactor, book: PriceBook
    ) -> dict[str, Any]:
        kind = span.kind
        if (
            kind == "span"
            and span.model
            and (span.input_tokens is not None or span.output_tokens is not None)
        ):
            kind = "generation"
        priced = price_span(span, kind, book)
        before = redactor.count
        row = {
            "project_id": project_id,
            "trace_id": span.trace_id,
            "id": span.span_id,
            "parent_id": span.parent_id,
            "name": _clean(span.name, 200) or "span",
            "kind": kind,
            "started_at": span.started_at,
            "ended_at": span.ended_at,
            "duration_ms": _millis(span.started_at, span.ended_at),
            "time_to_first_token_ms": span.time_to_first_token_ms,
            "status": span.status,
            "status_message": _clean(span.status_message, 2000),
            "level": "error" if span.status == "error" and span.level == "default" else span.level,
            "agent_name": _clean(span.agent_name, 120),
            "tool_name": _clean(span.tool_name, 120),
            "prompt_name": _clean(span.prompt_name, 120),
            "prompt_version": span.prompt_version if span.prompt_name else None,
            "model": _clean(span.model, 160),
            "provider": _clean(span.provider, 48),
            "model_parameters": span.model_parameters,
            "input_tokens": priced.input_tokens,
            "output_tokens": priced.output_tokens,
            "cached_tokens": min(span.cached_tokens or 0, priced.input_tokens),
            "total_tokens": priced.input_tokens + priced.output_tokens,
            "usage_estimated": priced.estimated,
            "input_cost": priced.input_cost,
            "output_cost": priced.output_cost,
            "total_cost": priced.input_cost + priced.output_cost,
            "cost_source": priced.source,
            "input": redactor.payload(span.input),
            "output": redactor.payload(span.output),
            "metadata": redactor.metadata(span.metadata),
        }
        row["redactions"] = redactor.count - before
        return row

    def _trace_row(
        self,
        project_id: uuid.UUID,
        trace_id: str,
        spans: list[SpanIn],
        declared: TraceIn | None,
        redactor: Redactor,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        started = min((s.started_at for s in spans), default=None)
        ended = max((s.ended_at for s in spans), default=None)
        started = started or (declared.timestamp if declared else None) or now
        ended = ended or started
        roots = sorted((s for s in spans if s.parent_id is None), key=lambda s: s.started_at)
        root = roots[0] if roots else None

        def first(attribute: str) -> Any:
            if declared is not None and getattr(declared, attribute, None):
                return getattr(declared, attribute)
            return next((v for s in spans if (v := getattr(s, attribute, None))), None)

        tags = (declared.tags if declared else []) or next((s.tags for s in spans if s.tags), [])
        return {
            "project_id": project_id,
            "id": trace_id,
            "name": _clean(
                (declared.name if declared and declared.name else None)
                or (root.trace_name or root.name if root else None)
                or "",
                200,
            ),
            "user_id": _clean(first("user_id"), 128),
            "session_id": _clean(first("session_id"), 128),
            "environment": _clean(first("environment"), 48) or "default",
            "release": _clean(first("release"), 64),
            "tags": [t.replace("\x00", "") for t in tags][:30],
            "started_at": started,
            "ended_at": ended,
            "duration_ms": _millis(started, ended),
            "status": "error" if any(s.status == "error" for s in spans) else "ok",
            "input": redactor.payload(
                declared.input if declared and declared.input else (root.input if root else None)
            ),
            "output": redactor.payload(
                declared.output if declared and declared.output else (root.output if root else None)
            ),
            "metadata": redactor.metadata(declared.metadata if declared else {}),
        }

    async def ingest(self, project: Project, batch: Batch, *, protocol: str) -> IngestResult:
        started = datetime.now(UTC)
        rules = RedactionRules.model_validate(project.redaction or {})
        redactor = rules.redactor()
        book = await self.c.prices.get(project.id)

        spans_by_trace: dict[str, list[SpanIn]] = defaultdict(list)
        for span in batch.spans:
            spans_by_trace[span.trace_id].append(span)
        declared = {t.trace_id: t for t in batch.traces}
        kept = self._decide(project, spans_by_trace)
        # A trace sent without spans (trace-level fields only) follows the rate alone.
        for trace_id in declared:
            if trace_id not in spans_by_trace and keep_by_rate(trace_id, project.sampling_rate):
                kept.add(trace_id)
        candidates = set(spans_by_trace) | set(declared)
        sampled_out = len(candidates - kept)

        span_rows: list[dict[str, Any]] = []
        trace_rows: list[dict[str, Any]] = []
        seen_prompts: set[tuple[str, int]] = set()
        for trace_id in sorted(kept):
            spans = spans_by_trace.get(trace_id, [])
            trace_rows.append(
                self._trace_row(project.id, trace_id, spans, declared.get(trace_id), redactor)
            )
            for span in spans:
                span_rows.append(self._span_row(project.id, span, redactor, book))
                if span.prompt_name and span.prompt_version:
                    seen_prompts.add((span.prompt_name[:120], span.prompt_version))

        if trace_rows:
            trace_ids = [row["id"] for row in trace_rows]
            # Serialise writers of the same trace: two batches of one trace must not
            # recompute its totals from each other's uncommitted spans.
            await self.session.execute(
                _LOCK, {"keys": [f"{project.id}:{trace_id}" for trace_id in trace_ids]}
            )
            await self.traces.upsert_traces(trace_rows)
            await self.traces.upsert_spans(span_rows)
            await self._attribute(project.id, trace_ids)
            await self.traces.refresh_aggregates(project.id, trace_ids)
            await PromptRepository(self.session).register_seen(project.id, seen_prompts)
        await self.session.commit()

        metrics.INGEST_SPANS.labels("stored").inc(len(span_rows))
        metrics.INGEST_SPANS.labels("sampled_out").inc(
            sum(len(spans_by_trace.get(t, [])) for t in candidates - kept)
        )
        if redactor.count:
            metrics.REDACTIONS.inc(redactor.count)
        metrics.INGEST_BATCHES.labels(protocol, "ok").inc()
        metrics.INGEST_DURATION.observe((datetime.now(UTC) - started).total_seconds())
        return IngestResult(
            accepted_spans=len(span_rows),
            accepted_traces=len(trace_rows),
            sampled_out_traces=sampled_out,
            redactions=redactor.count,
            rejected=batch.rejected,
        )

    async def _attribute(self, project_id: uuid.UUID, trace_ids: list[str]) -> None:
        """Fill in agent and tool names down each tree, touching only spans that change."""
        grouped = await self.traces.span_nodes_by_trace(project_id, trace_ids)
        updates: list[dict[str, Any]] = []
        for trace_id, nodes in grouped.items():
            resolved = resolve_attribution(nodes)
            for node in nodes:
                agent, tool = resolved[node.span_id]
                if (agent, tool) != (node.agent_name, node.tool_name):
                    updates.append(
                        {
                            "project_id": project_id,
                            "trace_id": trace_id,
                            "id": node.span_id,
                            "agent_name": agent,
                            "tool_name": tool,
                        }
                    )
        await self.traces.apply_attribution(updates)
