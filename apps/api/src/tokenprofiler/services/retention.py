"""Retention: remove traces older than each project's window, archiving them first on request.

Work is done in small batches, each in its own transaction, so a large backlog never holds
a long lock or one huge transaction. A batch is written to the archive store before it is
deleted: if the archive write fails the batch stays and the project is retried on the next
pass, so enabling archiving can never lose data silently.
"""

from __future__ import annotations

import gzip
import uuid
from datetime import UTC, datetime, timedelta

import orjson

from tokenprofiler.core import metrics
from tokenprofiler.core.logging import get_logger
from tokenprofiler.models import Project, Span, Trace
from tokenprofiler.repositories.alerting import AlertRepository
from tokenprofiler.repositories.projects import ProjectRepository
from tokenprofiler.repositories.traces import TraceRepository
from tokenprofiler.schemas.traces import SpanOut, TraceDetail
from tokenprofiler.services.container import Container

log = get_logger("tokenprofiler.retention")
RESOLVED_ALERT_DAYS = 90


def archive_key(project: Project, now: datetime) -> str:
    return f"{project.slug}/{now:%Y/%m/%d}/{now:%H%M%S}-{uuid.uuid4().hex[:8]}.ndjson.gz"


def encode_batch(rows: list[tuple[Trace, list[Span]]]) -> bytes:
    """One JSON object per trace, spans nested, gzip compressed."""
    lines = []
    for trace, spans in rows:
        document = TraceDetail.model_validate(trace).model_dump(mode="json")
        document["spans"] = [SpanOut.model_validate(span).model_dump(mode="json") for span in spans]
        lines.append(orjson.dumps(document))
    return gzip.compress(b"\n".join(lines) + b"\n", compresslevel=6)


async def purge_project(container: Container, project: Project, *, now: datetime) -> int:
    cutoff = now - timedelta(days=project.retention_days)
    batch = container.settings.retention_batch
    removed = 0
    while True:
        async with container.db.session() as session:
            traces = TraceRepository(session)
            ids = await traces.expired_ids(project.id, cutoff, batch)
            if not ids:
                return removed
            if project.archive_before_delete:
                rows = await traces.with_spans(project.id, ids)
                await container.archive.put(
                    archive_key(project, datetime.now(UTC)), encode_batch(rows)
                )
                metrics.RETENTION_ARCHIVED.inc(len(rows))
            deleted = await traces.delete(project.id, ids)
            await session.commit()
        metrics.RETENTION_DELETED.inc(deleted)
        removed += deleted
        if len(ids) < batch:
            return removed


async def run_retention(container: Container) -> dict[str, int]:
    """One pass over every project. Returns traces removed per project slug."""
    now = datetime.now(UTC)
    async with container.db.session() as session:
        projects = await ProjectRepository(session).all()
    report: dict[str, int] = {}
    for project in projects:
        try:
            report[project.slug] = await purge_project(container, project, now=now)
        except Exception:
            log.exception("retention_failed", project=project.slug)
    async with container.db.session() as session:
        await AlertRepository(session).purge_resolved(now - timedelta(days=RESOLVED_ALERT_DAYS))
        await session.commit()
    if any(report.values()):
        log.info("retention_purged", removed=report)
    return report
