"""Prometheus metrics, exposed at GET /metrics.

One API process per container (scale out with replicas, not uvicorn workers), so the default
registry is accurate without multiprocess mode. Labels never carry project ids or model
names: those are unbounded, so the per-project numbers live in the database instead.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "tokenprofiler_http_requests_total",
    "HTTP requests by route template.",
    ["method", "route", "status"],
)
HTTP_LATENCY = Histogram(
    "tokenprofiler_http_request_duration_seconds",
    "HTTP request latency by route template.",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)

INGEST_BATCHES = Counter(
    "tokenprofiler_ingest_batches_total",
    "Ingest requests by protocol (native, otlp-json, otlp-protobuf) and outcome.",
    ["protocol", "outcome"],
)
INGEST_SPANS = Counter(
    "tokenprofiler_ingest_spans_total",
    "Spans handled at ingest by disposition (stored, sampled_out).",
    ["disposition"],
)
INGEST_DURATION = Histogram(
    "tokenprofiler_ingest_duration_seconds",
    "Time to validate, redact, price and store one ingest batch.",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
REDACTIONS = Counter("tokenprofiler_redactions_total", "Values masked by PII redaction rules.")
RATE_LIMITED = Counter(
    "tokenprofiler_rate_limited_total", "Requests refused by a rate limit.", ["limit"]
)
DASHBOARD_CACHE = Counter(
    "tokenprofiler_dashboard_cache_total", "Dashboard aggregate lookups.", ["result"]
)
ALERTS_FIRED = Counter(
    "tokenprofiler_alerts_fired_total", "Alert events opened, by kind.", ["kind"]
)
WEBHOOKS = Counter(
    "tokenprofiler_webhook_deliveries_total", "Alert webhook deliveries by outcome.", ["outcome"]
)
RETENTION_DELETED = Counter(
    "tokenprofiler_retention_traces_deleted_total", "Traces removed by retention."
)
RETENTION_ARCHIVED = Counter(
    "tokenprofiler_retention_traces_archived_total", "Traces written to the archive store."
)
