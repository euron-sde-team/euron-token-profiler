# Operations

## Health and metrics

- `GET /livez`: the process is up. `GET /readyz`: PostgreSQL, Valkey and the archive store answer
  (503 with the failing check otherwise). Both are used by the container health checks.
- `GET /metrics` on the API and on the worker port (`WORKER_METRICS_PORT`) in Prometheus format.
  Keep it off the public load balancer. Useful series:

| Metric | Use |
| ------ | --- |
| `tokenprofiler_ingest_batches_total{protocol,outcome}` | Ingest volume by protocol |
| `tokenprofiler_ingest_spans_total{disposition}` | Stored versus sampled out |
| `tokenprofiler_ingest_duration_seconds` | The latency that matters when sizing |
| `tokenprofiler_redactions_total` | Masking activity |
| `tokenprofiler_rate_limited_total{limit}` | Keys hitting the limit |
| `tokenprofiler_dashboard_cache_total{result}` | Cache hit rate |
| `tokenprofiler_alerts_fired_total{kind}`, `tokenprofiler_webhook_deliveries_total{outcome}` | Alerting |
| `tokenprofiler_retention_traces_deleted_total`, `..._archived_total` | Retention progress |

## Routine tasks

- **Create a person**: `tokenprofiler user create --email ... --name ... --role admin`
  (`make aws-cli ARGS=...` on AWS). The command works without a terminal.
- **Run retention now**: `tokenprofiler retention`.
- **Export the API description**: `make openapi`.
- **Rotate a secret**: `SESSION_SECRET` signs everyone out; `API_KEY_PEPPER` invalidates every
  project key (create new ones first); `ENCRYPTION_KEY` makes stored webhook URLs unreadable, so
  re-enter them.

## Capacity

Disk is the slow variable: a span with payloads is typically 1 to 5 KB. Lower retention, switch off
payload storage, or sample, in that order of preference. The archive keeps what retention removes,
compressed, outside the database.

## Upgrades

Images are tagged by git commit. The API applies migrations at start under an advisory lock, so a
rolling deploy is safe; migrations are additive. The builtin price table is refreshed at start
without touching edited rows.
