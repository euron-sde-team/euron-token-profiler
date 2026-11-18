# Changelog

All notable changes are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/)
and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-18

First release.

### Added

- Ingest: a native batch endpoint, OTLP/HTTP in JSON and protobuf (gzip accepted), per-key rate limits
  and per-item validation.
- Python SDK (`tokenprofiler-sdk`): `@observe`, nested spans through `contextvars`, a background sender
  with retries and a bounded queue, prompt fetching with a cache, `usage_from` for common clients.
- Cost and token attribution per prompt version, model, agent and tool, from a builtin table of 46 models
  with per-project overrides; estimated usage is flagged and unpriced models are marked.
- Privacy: seven built-in masking detectors, validated custom patterns, a no-payload mode, payload limits,
  sampling by trace id that keeps errors and slow spans, retention with an encrypted archive.
- Budgets and alert rules with webhook notification, escalation and resolution.
- Dashboard: overview, trace list and search, trace waterfall and span panel, prompts with versions and
  labels, models, agents and tools, pricing, budgets and alerts, project keys, settings, people and audit.
- Docker Compose stack on the Floci AWS emulator, Terraform for AWS (`aws-dev`, `aws-prod`), GitHub
  workflows, a seeded demo with two weeks of traces.
