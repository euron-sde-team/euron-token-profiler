# Low-level design

## Backend layout

```text
apps/api/src/tokenprofiler/
  core/          settings, logging, errors, security, rate limits, secret box, metrics, request context
  db/            engine and sessions, declarative base, advisory-locked migration runner
  models/        SQLAlchemy models (one file per aggregate)
  migrations/    Alembic revisions (0001 creates everything)
  ingest/        pure, I/O free logic: types, native + OTLP parsing, redaction, pricing,
                 sampling, token estimates, agent/tool attribution
  pricing/       the shipped price table (prices.json)
  schemas/       Pydantic request and response models
  repositories/  the only code that touches the database
  services/      business rules and transactions
  api/           routes (URL and auth dependency only), dependencies, router
  integrations/  boto3 clients, the archive store (local directory or S3)
  demo/          the deterministic workload and the demo seeder
  main.py        application factory       worker.py  background loops       cli.py  operator CLI
```

Layer rules: routes call services; services call repositories and the pure `ingest` modules;
repositories hold every query. `core` and `ingest` import nothing from the layers above them.

## The ingest pipeline

`services/ingest.py` (`IngestService.ingest`) takes a project and a normalised `Batch`.

1. **Rules.** The project's `redaction` JSON is validated into `RedactionRules` and compiled into a
   `Redactor`. The price book for the project is read from the process cache.
2. **Sampling.** Spans are grouped by trace. A trace is kept when `sha256(trace_id)` (first 8
   bytes, as a fraction) is below the sampling rate, or when `keep_errors` and any span failed, or
   when `keep_slow_ms` is set and any span ran at least that long. The decision is per trace, so a
   kept trace is whole. A trace sent with no spans follows the rate only.
3. **Per span** (`_span_row`):
   - kind fix: a plain `span` with a model and token counts becomes a `generation`;
   - `price_span`: metered kinds only. Missing token counts are estimated from the original
     payload (about 4 ASCII characters per token, one per other character) and flagged
     `usage_estimated`. Cost is `reported` (caller supplied), `table` (price book match) or
     `none` (unknown model, cost zero, flagged);
   - payloads and metadata are masked and truncated **after** pricing, so an estimate is never
     computed from already-shortened text.
4. **Per trace** (`_trace_row`): name from the declared trace or the root span; user, session,
   environment, release and tags from the declared trace or the first span that has them; input
   and output from the root span's already-masked row.
5. **Write**, in one transaction: advisory lock over the batch's trace ids (sorted, so two batches
   never deadlock), upsert traces, upsert spans (400 rows per statement, `ON CONFLICT` replaces),
   attribution, aggregate refresh, prompt registration, commit.

### Attribution

`ingest/attribution.py` walks parents. A span's agent is its own `agent_name`, else its name when
its kind is `agent`, else its nearest ancestor's; tools work the same way. Only rows whose result
differs from what is stored are updated, in one bulk update by primary key. Missing parents,
parents arriving later and cycles are handled (a span with an unknown parent is a root).

### Aggregate refresh

One `UPDATE traces ... FROM (SELECT ... GROUP BY trace_id)` per 1,000 traces recomputes: start,
end and duration, status (error if any span failed), span, error and generation counts, token and
cost sums over metered spans, and the distinct models, agents, tools and prompts arrays. The arrays
are GIN indexed, so the list filters never touch `spans`.

## Protocol adapters

- **Native** (`POST /v1/ingest`): `{traces: [...], spans: [...]}`. Each item is validated on its
  own; bad ones are returned under `rejected`, the rest are stored.
- **OTLP** (`POST /v1/otlp/v1/traces`): JSON, or protobuf decoded with `opentelemetry-proto` into
  the same dictionary shape (ids arrive base64 and are converted to hex). `Content-Encoding: gzip`
  and `deflate` are inflated with a bounded decompressor. Mapping:

| Span field        | Attributes read, in order                                                          |
| ----------------- | ---------------------------------------------------------------------------------- |
| kind              | `tokenprofiler.span.kind`, `openinference.span.kind`, `gen_ai.operation.name`, `traceloop.span.kind`, else model plus usage means generation |
| model             | `gen_ai.response.model`, `gen_ai.request.model`, `llm.model_name`, `ai.model.id`   |
| input tokens      | `gen_ai.usage.input_tokens`, `gen_ai.usage.prompt_tokens`, `llm.token_count.prompt` |
| output tokens     | `gen_ai.usage.output_tokens`, `gen_ai.usage.completion_tokens`, `llm.token_count.completion` |
| cached tokens     | `gen_ai.usage.cache_read_input_tokens`, `gen_ai.usage.cached_input_tokens`         |
| agent, tool       | `gen_ai.agent.name`, `gen_ai.tool.name` (or `tokenprofiler.*.name`)               |
| prompt            | `tokenprofiler.prompt.name`, `tokenprofiler.prompt.version`                        |
| user, session     | `user.id`, `enduser.id`; `session.id`, `gen_ai.conversation.id`                    |
| environment       | `tokenprofiler.environment`, `deployment.environment(.name)`                       |
| input, output     | `tokenprofiler.input`, `gen_ai.input.messages`, `gen_ai.prompt`, `input.value` (and the output twins) |
| status            | OTLP status code 2, `error.type`, or an `exception` event                          |

The response is an `ExportTraceServiceResponse`; rejected spans appear under `partialSuccess`.

## Pricing

`ingest/pricing.py`. `normalize_model` lowercases, drops a provider prefix (`openai/`,
`bedrock/anthropic.`) and Bedrock revisions. Entries are ordered project overrides first, then the
longest model name, and the first regular expression that matches wins, so `gpt-4o-mini` is tried
before `gpt-4o`. Cost is `fresh * input + cached * cached_rate + output`, in `Decimal`, per million
tokens, quantised to 8 places; cached tokens bill at the input rate when no cached price exists.
`pricing/prices.json` ships 46 rows and is upserted at API and worker start; rows people edited are
never overwritten. `PriceBooks` caches one book per project for `PRICE_CACHE_TTL_S` seconds and an
edit invalidates the local process immediately.

## Redaction

`ingest/redaction.py`. Built-in detectors run in a fixed order (email, card with a Luhn check, SSN,
phone, IPv4, API keys, JWT) followed by custom patterns. Strings anywhere inside input, output and
metadata are masked; numbers, booleans and keys are not touched. Strings are cut to
`max_payload_chars` first, so no rule scans unbounded text. Custom patterns are validated when
saved (length, compiles, no nested repetition) because Python's `re` has no timeout.

## Dashboards and the cache

`services/dashboards.py`. A relative range ends on a 30 second boundary; the cache key is
`dash:<project>:<kind>:<sha1(params)>`; entries live `DASHBOARD_CACHE_TTL_S` seconds. The overview
runs four aggregates (current and previous KPIs, a bucketed series, cost by model per bucket) and
fills empty buckets with zeros. Bucket width is the smallest of 1, 5, 15, 30 minutes, 1, 3, 6, 12
hours or a day that keeps the chart near 72 points (`date_bin` on a fixed origin).

## Budgets and alerts

`services/alerts.py`, run by the worker every `ALERT_INTERVAL_S` under the Valkey lock
`lock:worker:alerts`.

- A **budget** compares spend in the current UTC day, ISO week or month (optionally narrowed to one
  model, agent, tool or prompt) with its limit: `ok`, `warning` at the warn percentage, `exceeded`
  at the limit.
- An **alert rule** compares a metric (`error_rate`, `p95_latency_ms`, `cost_usd`,
  `trace_count`) over a trailing window with a threshold. Fewer traces than `min_traces` means no
  data, never an alert (except `trace_count`, which exists to notice silence).
- One event per source is open at a time (a partial unique index on `source_id where state =
  'firing'`). A firing source opens an event, an escalation (warning to critical) updates it and
  notifies again, recovery resolves it. Notifications POST JSON to the project webhook
  (`alert.firing`, `alert.escalated`, `alert.resolved`); the URL is sealed at rest, validated on
  save and again on delivery (public addresses only), with a timeout and no redirects.

## Retention and archive

`services/retention.py`, every `RETENTION_INTERVAL_S` under `lock:worker:retention`. For each
project: select up to `RETENTION_BATCH` trace ids older than `retention_days`; if
`archive_before_delete`, write one gzip NDJSON object (`<slug>/<yyyy>/<mm>/<dd>/<time>-<id>.ndjson.gz`,
one trace with nested spans per line) to the archive store and only then delete the batch (spans
cascade). An archive failure aborts the project's pass and leaves the data. Resolved alert events
older than 90 days are purged.

## Authentication and authorisation

- People: email and Argon2id password; the session is an HS256 JWT in an httpOnly cookie (and
  returned for bearer use) carrying a `session_version`; changing a password or a role bumps the
  version, which ends every other session at once. Logout denylists the token id in Valkey.
- Roles: `admin` (everything), `member` (prompts, prices, budgets, alert rules, keys, redaction
  preview), `viewer` (read only). Writes are guarded by `WriterDep`, admin actions by `AdminDep`.
- Cookie-authenticated unsafe requests must come from the web app's origin (CSRF).
- Project keys (`tp_<10 chars>_<43 chars>`): only an HMAC-SHA256 of the secret, keyed by the pepper,
  is stored. A key authorises ingest and prompt fetch for its project only.

## Errors

Every error is `{"error": {"code", "message", "request_id", "details?"}}` with `X-Request-Id`.
Validation failures are 422 with the offending locations in `details`.

## Background and shutdown

The API closes its Valkey and database pools on SIGTERM after uvicorn drains requests. The worker
finishes its current pass before exiting, so a retention batch is never left between its archive
write and its delete.

## Testing seams

Pure modules (`ingest/*`, period maths, bucket sizing) are unit tested without I/O. Services run
against real Postgres, Valkey and Floci in the integration suite; the HTTP layer is exercised over
ASGI. The demo workload is deterministic (seeded RNG) and flows through the same ingest service.
