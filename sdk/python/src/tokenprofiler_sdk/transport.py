"""A background sender: batches events, retries transient failures, never blocks the caller."""

from __future__ import annotations

import contextlib
import logging
import queue
import threading
import time
from typing import Any

import httpx

log = logging.getLogger("tokenprofiler_sdk")

_STOP = object()
_RETRYABLE = {408, 425, 429, 500, 502, 503, 504}


class Sender:
    """Events go onto a bounded queue and a daemon thread posts them in batches.

    When the queue is full the oldest behaviour a caller could want is "never slow my
    application down", so the new event is dropped and counted instead of blocking.
    """

    def __init__(
        self,
        client: httpx.Client,
        *,
        flush_at: int,
        flush_interval: float,
        max_queue: int,
        max_retries: int,
        backoff: float = 0.5,
    ) -> None:
        self._client = client
        self._flush_at = flush_at
        self._interval = flush_interval
        self._retries = max_retries
        self._backoff = backoff
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=max_queue)
        self._lock = threading.Lock()
        self.sent = 0
        self.dropped = 0
        self.failed = 0
        self._thread = threading.Thread(target=self._run, name="tokenprofiler-sender", daemon=True)
        self._thread.start()

    def add(self, kind: str, item: dict[str, Any]) -> None:
        try:
            self._queue.put_nowait((kind, item))
        except queue.Full:
            with self._lock:
                self.dropped += 1

    def flush(self, timeout: float = 30.0) -> bool:
        """Block until everything queued so far has been sent or given up on."""
        barrier = threading.Event()
        try:
            self._queue.put(("flush", barrier), timeout=timeout)
        except queue.Full:
            return False
        return barrier.wait(timeout)

    def shutdown(self, timeout: float = 30.0) -> None:
        self.flush(timeout)
        with contextlib.suppress(queue.Full):
            self._queue.put_nowait(_STOP)
        self._thread.join(timeout)

    def _run(self) -> None:
        spans: list[dict[str, Any]] = []
        traces: list[dict[str, Any]] = []
        deadline = time.monotonic() + self._interval
        while True:
            timeout = max(0.0, deadline - time.monotonic())
            try:
                entry = self._queue.get(timeout=timeout)
            except queue.Empty:
                entry = None
            if entry is _STOP:
                self._post(traces, spans)
                return
            if entry is not None:
                kind, payload = entry
                if kind == "span":
                    spans.append(payload)
                elif kind == "trace":
                    traces.append(payload)
                elif kind == "flush":
                    self._post(traces, spans)
                    traces, spans = [], []
                    payload.set()
            if len(spans) + len(traces) >= self._flush_at or time.monotonic() >= deadline:
                if spans or traces:
                    self._post(traces, spans)
                    traces, spans = [], []
                deadline = time.monotonic() + self._interval

    def _post(self, traces: list[dict[str, Any]], spans: list[dict[str, Any]]) -> None:
        if not traces and not spans:
            return
        body = {"traces": traces, "spans": spans}
        for attempt in range(self._retries + 1):
            try:
                response = self._client.post("/v1/ingest", json=body)
            except httpx.HTTPError as exc:
                log.warning(
                    "tokenprofiler: send failed (%s), attempt %d", type(exc).__name__, attempt + 1
                )
            else:
                if response.status_code < 300:
                    with self._lock:
                        self.sent += len(spans) + len(traces)
                    return
                if response.status_code not in _RETRYABLE:
                    log.error(
                        "tokenprofiler: batch rejected with HTTP %d, dropping it",
                        response.status_code,
                    )
                    break
                retry_after = response.headers.get("retry-after")
                if retry_after and retry_after.isdigit():
                    time.sleep(min(int(retry_after), 30))
                    continue
            time.sleep(self._backoff * (2**attempt))
        with self._lock:
            self.failed += len(spans) + len(traces)
