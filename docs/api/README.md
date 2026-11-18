# API

The machine-readable description is [openapi.json](openapi.json), exported from the application
with `make openapi`. A running stack serves the same at <http://localhost:8210/docs>.

Two planes, two kinds of credential:

| Plane         | Prefix    | Credential                                      | For                              |
| ------------- | --------- | ----------------------------------------------- | -------------------------------- |
| Ingest        | `/v1`     | `Authorization: Bearer tp_...` (or `x-api-key`) | SDKs and OpenTelemetry exporters |
| Control plane | `/api/v1` | The session cookie, or `Bearer <session token>` | The dashboard and automation     |

Every error has one shape and every response carries `X-Request-Id`:

```json
{
  "error": {
    "code": "validation_failed",
    "message": "Some fields are invalid.",
    "request_id": "9f3c...",
    "details": [{ "loc": ["body", "limit_usd"], "message": "..." }]
  }
}
```

## Ingest plane

| Method and path           | What it does                                                                                                                                                                |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /v1/ingest`         | Native batch of traces and spans. Items are validated one by one; the response lists `accepted_spans`, `accepted_traces`, `sampled_out_traces`, `redactions` and `rejected` |
| `POST /v1/otlp/v1/traces` | OpenTelemetry OTLP/HTTP, `application/json` or `application/x-protobuf`, gzip accepted. Standard `ExportTraceServiceResponse`, with `partialSuccess` for unusable spans     |
| `GET /v1/prompts/{name}`  | A managed prompt: `?version=3`, `?label=staging`, or production by default (newest if there is no production)                                                               |

`429` carries `Retry-After`; limits are per key (`INGEST_RATE_LIMIT` requests a minute).

## Control plane

All project resources live under `/api/v1/projects/{project_id}`.

| Area             | Endpoints                                                                                                      |
| ---------------- | -------------------------------------------------------------------------------------------------------------- |
| Session          | `POST /auth/login`, `/auth/setup`, `/auth/logout`, `/auth/password`; `GET, PATCH /auth/me`                     |
| People (admin)   | `GET, POST /users`, `PATCH /users/{id}`                                                                        |
| Projects         | `GET, POST /projects`; `GET, PATCH, DELETE /projects/{id}` (settings: sampling, redaction, retention, webhook) |
| Keys             | `GET, POST .../keys`, `DELETE .../keys/{id}` (the secret is shown once, on creation)                           |
| Traces           | `GET .../traces` (filters below), `GET .../traces/{id}` (trace plus spans), `GET .../traces/facets`            |
| Metrics          | `GET .../metrics/overview?range=24h`, `GET .../metrics/breakdown?dimension=model\|agent\|tool\|prompt`         |
| Prompts          | `GET, POST .../prompts`, `GET .../prompts/{name}`, `PUT .../prompts/{name}/label`                              |
| Prices           | `GET .../prices`, `GET .../prices/lookup?model=`, `PUT .../prices`, `DELETE .../prices/{id}`                   |
| Budgets, alerts  | `GET .../alerts`, `GET .../alert-events`, `POST, PUT, DELETE .../budgets`, `.../alert-rules`                   |
| Privacy          | `POST .../redaction/test` (preview masking on sample text)                                                     |
| Archives (admin) | `GET .../archives`, `GET .../archives/download?key=`                                                           |
| System           | `GET /system/info` (public), `GET /audit` (admin)                                                              |

Trace list filters: `range` (1h, 6h, 24h, 7d, 14d, 30d) or `start` and `end`, `status`, `q` (name,
id prefix, user or session), `model`, `agent`, `tool`, `prompt`, `environment`, `user_id`,
`session_id`, `tag`, `min_cost`, `min_duration_ms`, `sort` (started_at, cost, duration, tokens),
`order`, `limit` (1 to 200) and `offset`. Lists return `{items, total, limit, offset}`; the trace
list also returns `total_capped` because counting stops at 10,000.

Decimals (money, prices) are strings so no precision is lost.

## Example

```bash
curl -s -X POST http://localhost:8210/api/v1/auth/login -H 'content-type: application/json' \
  -d '{"email":"admin@example.com","password":"..."}' -c jar.txt >/dev/null
PROJECT=$(curl -s -b jar.txt http://localhost:8210/api/v1/projects | jq -r '.items[0].id')
curl -s -b jar.txt "http://localhost:8210/api/v1/projects/$PROJECT/metrics/breakdown?dimension=agent&range=7d" | jq '.items[] | {key, cost, calls}'
```
