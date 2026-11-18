# Quickstart: run it locally

Everything runs in Docker on your machine: PostgreSQL, Valkey, the Floci AWS emulator, the API,
the worker and the web app. No cloud account and no API key.

## Prerequisites

Docker with Compose v2 (Colima works), GNU make, 8 GB of RAM. For development as well: Python 3.12
with [uv](https://docs.astral.sh/uv/), Node 22 and pnpm 9 (`corepack enable`).

## Start

```bash
make up      # builds the images, provisions the emulator with Terraform, starts everything
make demo    # people, two projects, prompts, budgets, alerts and two weeks of traces
```

The first `make up` takes a few minutes (image builds, Terraform provider download). Then open:

| What      | Address                       |
| --------- | ----------------------------- |
| Dashboard | http://localhost:3210         |
| API docs  | http://localhost:8210/docs    |
| Ingest    | http://localhost:8210/v1      |

`make env` writes `deploy/compose/.env` with random local-only secrets and the demo password
(`TP_DEMO_PASSWORD`). `make demo` prints the sign-in emails and the ingest key of the demo project:

- `admin@example.com`: everything
- `maya@example.com`: a member (prompts, budgets, keys)
- `viewer@example.com`: read only

Without `make demo`, open the dashboard and the first-run page creates the first administrator.

## Send your first trace

Create a key under API keys, then:

```bash
curl -X POST http://localhost:8210/v1/ingest \
  -H "Authorization: Bearer tp_..." -H "Content-Type: application/json" \
  -d '{"spans":[{"id":"s1","trace_id":"t1","name":"hello","kind":"generation",
        "start_time":"2026-11-18T10:00:00Z","model":"gpt-4o",
        "usage":{"input":812,"output":96},"input":"Hi","output":"Hello"}]}'
```

It appears under Traces within a minute with its cost computed from the price table. The
[instrumentation guide](instrumentation.md) covers the Python SDK and OpenTelemetry.

## Everyday commands

| Command                 | What it does                                             |
| ----------------------- | -------------------------------------------------------- |
| `make ps` / `make logs` | Stack status, tail logs (`SERVICE=api`)                  |
| `make down`             | Stop everything and delete its volumes                   |
| `make test`             | Unit tests (pytest for the API and SDK, Vitest)          |
| `make test-integration` | API tests on real Postgres, Valkey and Floci             |
| `make e2e` / `make qa`  | Playwright journeys; crawl every page at two widths      |
| `make lint typecheck`   | ruff, ESLint, Prettier, mypy (strict), tsc               |
| `make openapi`          | Regenerate `docs/api/openapi.json`                       |

## Developing without Docker for the app

`scripts/test-deps.sh` starts only Postgres, Valkey and Floci. Then:

```bash
cd apps/api && uv sync
export DATABASE_URL=postgresql+asyncpg://tokenprofiler:tokenprofiler@localhost:5461/tokenprofiler
export REDIS_URL=redis://localhost:6421/0 MIGRATE_ON_BOOT=true
uv run uvicorn tokenprofiler.main:create_app --factory --port 8210 --reload
pnpm install && pnpm dev          # the dashboard on http://localhost:3210
```
