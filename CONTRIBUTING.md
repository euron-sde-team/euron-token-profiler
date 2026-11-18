# Contributing

Thanks for helping improve Euron TokenProfiler. This guide covers the workflow, the bar a
change has to clear, and the conventions the codebase follows.

## Ground rules

- **Open an issue first** for anything larger than a bug fix or a docs tweak, so we can
  agree on the approach before you invest time.
- **One concern per pull request.** A refactor and a feature are two pull requests.
- **Security issues go through private reporting**, never a public issue. See
  [SECURITY.md](SECURITY.md).
- By contributing you agree your work is released under the [MIT License](LICENSE).

## Development setup

Requirements: Docker with Compose v2, Python 3.12 with [uv](https://docs.astral.sh/uv/),
Node 22 and pnpm 9 (`corepack enable`).

```bash
pnpm install                 # web app and browser tests
(cd apps/api && uv sync)     # API, worker and CLI
make up                      # the whole stack on the local AWS emulator
make demo                    # demo accounts, two weeks of traces, prompts, budgets and alerts
make test                    # unit tests (pytest, Vitest)
```

[docs/guides/quickstart-local.md](docs/guides/quickstart-local.md) walks through the local
stack in detail.

## Before you open a pull request

Each of these must pass:

```bash
make lint typecheck test       # ruff, mypy (strict), ESLint, tsc, pytest, Vitest
make test-integration          # API against real Postgres, Valkey and the AWS emulator
make e2e qa                    # when you touched a user flow or the web app
make tf-fmt tf-validate tf-lint tf-security   # when you touched infra/terraform
make sanitize                  # no credentials, account ids or resource ids
```

## Conventions

**Layers (api).** Routes declare the URL and the auth dependency and nothing else; services
hold the business rules and own their transactions; repositories are the only code that
touches the database. The pure ingest logic (`ingest/`: OTLP and native parsing, redaction,
pricing, sampling, attribution) has no I/O and is unit tested on its own.
[apps/api/README.md](apps/api/README.md) has the rules and a reference resource to read first.

**One normalised shape.** A new ingest protocol converts its payload to `ingest/types.py`
(`SpanIn`) and gets sampling, redaction, pricing, attribution and storage for free.

**Configuration is validated.** A new environment variable is documented in
[docs/guides/configuration.md](docs/guides/configuration.md) in the same pull request, and
security-relevant ones are enforced at boot in `apps/api/src/tokenprofiler/core/config.py`.

**Database changes are new migrations.** Add a revision under
`apps/api/src/tokenprofiler/migrations/versions/`. Never edit an applied migration.

**Comments explain why.** The code says what it does. Comments are for the constraint, the
incident or the trade-off that made it this way.

**Style.** ruff (lint and format) and mypy strict for Python; Prettier and ESLint with
TypeScript strict for the web app.

## Commit messages

Imperative mood with a scope: `ingest: keep error traces under sampling`,
`web: show cost per tool on the agents page`. Explain the _why_ in the body when it is not obvious.

## Architecture decisions

A change that alters a documented decision (the span model, attribution rules, the
redaction approach, deployment topology, layering) needs a new ADR in
[docs/architecture/adr/](docs/architecture/adr/), using the existing ones as a template.
