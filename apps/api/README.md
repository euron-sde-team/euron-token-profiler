# TokenProfiler API

FastAPI service: ingest endpoints (native and OpenTelemetry) and the control plane, plus the
worker and the operator CLI, all in one Python package (`tokenprofiler`).

```bash
uv sync
uv run pytest tests/unit -q                       # unit tests
scripts/test-deps.sh && uv run pytest tests/integration -m integration   # real Postgres, Valkey, Floci
uv run ruff check . && uv run mypy                # lint and strict types
uv run tokenprofiler --help                       # migrate, user create, demo seed, retention, openapi
```

The design is in [docs/architecture](../../docs/architecture/LLD.md). The rules that matter when
changing code:

- Routes declare the URL and the auth dependency and nothing else; services own transactions;
  repositories are the only code that queries.
- `ingest/` is pure (no I/O) and is where parsing, masking, pricing, sampling and attribution live.
- Every query on project data is scoped by `project_id`; cache keys contain it too.
- A reference to read first: `services/ingest.py` (the pipeline) with `tests/integration/test_ingest.py`.
