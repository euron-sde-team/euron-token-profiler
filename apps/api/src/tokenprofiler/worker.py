"""The background worker: alert evaluation and retention.

    python -m tokenprofiler.worker

- Each loop takes a Valkey lock for the length of its interval, so any number of workers can
  run and only one does the work per round.
- SIGTERM stops the loops at their next wake-up; a pass in progress finishes first, so a
  retention batch is never abandoned between its archive write and its delete.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from collections.abc import Awaitable, Callable

from prometheus_client import start_http_server

from tokenprofiler.core.config import get_settings
from tokenprofiler.core.logging import configure_logging, get_logger
from tokenprofiler.db.migrate import migrate
from tokenprofiler.services.alerts import evaluate_all
from tokenprofiler.services.container import Container, build_container
from tokenprofiler.services.prices import sync_builtin_prices
from tokenprofiler.services.retention import run_retention

log = get_logger("tokenprofiler.worker")


async def periodic(
    container: Container,
    stop: asyncio.Event,
    *,
    name: str,
    interval_s: float,
    job: Callable[[], Awaitable[object]],
) -> None:
    lock = f"lock:worker:{name}"
    while not stop.is_set():
        try:
            if await container.redis.set(lock, b"1", ex=max(1, int(interval_s) - 1), nx=True):
                await job()
        except Exception:
            log.exception("worker_job_failed", job=name)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), interval_s)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    if settings.migrate_on_boot:
        await migrate(settings)
    if port := int(os.environ.get("WORKER_METRICS_PORT", "0")):
        start_http_server(port)
    container = await build_container(settings)
    await sync_builtin_prices(container)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    log.info(
        "worker_started",
        alert_interval_s=settings.alert_interval_s,
        retention_interval_s=settings.retention_interval_s,
        archive=settings.archive_store,
    )
    jobs = [
        asyncio.create_task(
            periodic(
                container,
                stop,
                name="alerts",
                interval_s=settings.alert_interval_s,
                job=lambda: evaluate_all(container),
            )
        ),
        asyncio.create_task(
            periodic(
                container,
                stop,
                name="retention",
                interval_s=settings.retention_interval_s,
                job=lambda: run_retention(container),
            )
        ),
    ]
    try:
        await stop.wait()
    finally:
        await asyncio.gather(*jobs, return_exceptions=True)
        await container.close()
        log.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
