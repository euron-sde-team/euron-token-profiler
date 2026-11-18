# Configuration

All settings are environment variables, validated once at start (`core/config.py`). Empty values
count as unset. In production the process refuses to start while any development default is in
use; it lists every problem at once.

## Required in production

| Variable         | Meaning                                                              |
| ---------------- | -------------------------------------------------------------------- |
| `SESSION_SECRET` | Signs session tokens. 32 or more characters                          |
| `API_KEY_PEPPER` | Keys the hash of project API keys. 32 or more characters             |
| `ENCRYPTION_KEY` | Seals webhook URLs. 32 or more characters, different from the others |
| `COOKIE_SECURE`  | Must be `true` behind HTTPS                                          |
| `CORS_ORIGINS`   | Explicit web origins, never `*`                                      |
| `DATABASE_URL`   | `postgresql+asyncpg://...` (on AWS without a password, see below)    |
| `REDIS_URL`      | Valkey or Redis                                                      |

## Application

| Variable                  | Default               | Meaning                                                |
| ------------------------- | --------------------- | ------------------------------------------------------ |
| `APP_ENV`                 | `development`         | `development`, `test` or `production`                  |
| `PRODUCT_NAME`            | `Euron TokenProfiler` | Name shown in the UI and the API docs                  |
| `LOG_LEVEL`, `LOG_FORMAT` | `info`, `json`        | `console` format for reading logs by eye               |
| `WEB_URL`, `API_URL`      | localhost ports       | Used for CSRF checks and links in notifications        |
| `MAX_REQUEST_MB`          | `16`                  | Largest accepted request body                          |
| `ALLOW_SIGNUP`            | `false`               | Let anyone create a member account                     |
| `SESSION_TTL_HOURS`       | `168`                 | Session lifetime                                       |
| `RATE_LIMIT_LOGIN`        | `10`                  | Sign-in attempts per minute per address                |
| `DATABASE_SECRET_ARN`     | unset                 | Read the database password from this secret (AWS)      |
| `DATABASE_POOL_SIZE`      | `10`                  | Connections per process (plus `DATABASE_MAX_OVERFLOW`) |
| `MIGRATE_ON_BOOT`         | `false`               | Apply migrations when the API or worker starts         |

## Ingest

| Variable              | Default | Meaning                                          |
| --------------------- | ------- | ------------------------------------------------ |
| `INGEST_RATE_LIMIT`   | `1200`  | Requests per minute per project key              |
| `MAX_BATCH_ITEMS`     | `5000`  | Spans plus traces accepted in one request        |
| `MAX_DECOMPRESSED_MB` | `64`    | Largest body after gzip or deflate is removed    |
| `PRICE_CACHE_TTL_S`   | `30`    | How long a process reuses a project's price book |

Sampling, masking, retention and the webhook are per project, in the dashboard under Settings.

## Dashboards, alerts, retention

| Variable                      | Default | Meaning                                               |
| ----------------------------- | ------- | ----------------------------------------------------- |
| `DASHBOARD_CACHE_TTL_S`       | `30`    | Overview and breakdown cache; `0` disables it         |
| `ALERT_INTERVAL_S`            | `30`    | How often the worker evaluates budgets and rules      |
| `RETENTION_INTERVAL_S`        | `600`   | How often the worker enforces retention               |
| `RETENTION_BATCH`             | `500`   | Traces deleted per transaction                        |
| `DEFAULT_RETENTION_DAYS`      | `30`    | Retention of a new project                            |
| `WEBHOOK_ALLOW_PRIVATE_HOSTS` | `false` | Development only: allow webhooks to private addresses |
| `WEBHOOK_TIMEOUT_S`           | `5`     | Webhook delivery timeout                              |

## Archive

| Variable           | Default        | Meaning                                         |
| ------------------ | -------------- | ----------------------------------------------- |
| `ARCHIVE_STORE`    | `local`        | `local` (a directory) or `s3`                   |
| `ARCHIVE_DIR`      | `data/archive` | Directory for the local store                   |
| `S3_BUCKET`        | unset          | Required for `s3`                               |
| `S3_PREFIX`        | `archive`      | Key prefix inside the bucket                    |
| `S3_KMS_KEY_ID`    | unset          | Key id, ARN or alias for SSE-KMS                |
| `AWS_REGION`       | `us-east-1`    |                                                 |
| `AWS_ENDPOINT_URL` | unset          | Set only for an emulator; production refuses it |

## Worker and demo

`WORKER_METRICS_PORT` (worker only) serves Prometheus metrics. `DEMO_PASSWORD` is read by
`tokenprofiler demo seed` only, and the seed refuses to run when `APP_ENV=production`.

## Compose overrides

`deploy/compose/.env` may set `TP_WEB_PORT`, `TP_API_PORT`, `TP_PG_PORT`, `TP_REDIS_PORT`,
`TP_FLOCI_PORT`, `TP_LOG_LEVEL`, `TP_PRODUCT_NAME` and `TP_NODE_NAME`. All ports bind to
`127.0.0.1`.
