# Testing

| Suite            | Command                 | What it covers                                                               |
| ---------------- | ----------------------- | ---------------------------------------------------------------------------- |
| API unit         | `make test`             | Parsing, redaction, pricing, sampling, attribution, period maths, workload   |
| SDK unit         | `make test`             | Span nesting, `@observe`, retries, queue overflow, prompts                   |
| Web unit         | `make test`             | Formatting, URL state, the span tree layout, snippets                        |
| API integration  | `make test-integration` | The whole API on real PostgreSQL, Valkey and Floci                           |
| Browser journeys | `make e2e`              | Sign in, filters, trace detail, keys, prompts, budgets, settings             |
| QA crawl         | `make qa`               | Every page at 1440 and 390 px, light and dark; console, requests, links, axe |

## Integration tests

`scripts/test-deps.sh` starts Postgres, Valkey and Floci from the compose files (ports 5461, 6421,
4621). The suite makes its own database (`tokenprofiler_test`, recreated per run), uses Valkey
database 15 and uniquely named buckets, so development data is never touched. Each test gets a
fresh project and key, so tests never see each other's traces. The suite starts the real
application over ASGI and checks, among other things:

- a trace is priced, attributed and totalled correctly, including cache discounts and estimated usage;
- masking removes values before storage and counts them; sampling keeps errors and slow spans;
- OTLP in JSON, gzip JSON and protobuf produce the same stored result; decompression bombs fail;
- filters, sorts, search and pagination; breakdowns add up; the cache hits and is project scoped;
- prompt versions, labels and fetch; price overrides apply to new spans only;
- budgets and rules open, escalate and resolve exactly one event, and notify a webhook;
- retention deletes with cascade, archives locally and to S3 on Floci, and keeps data if archiving fails;
- the demo seed produces the workspace the screenshots rely on and its totals reconcile;
- roles, session revocation, last-admin protection and the SSRF guard.

## Browser tests

`make up && make demo` first. The suites sign in as the demo people (the password is in
`deploy/compose/.env`) and reuse one saved session per role to stay under the sign-in limit.
`make screenshots` captures 1440x900 images at 2x into `docs/assets/screenshots/` plus the tour GIF;
run it on a fresh stack before `make e2e`, which creates its own keys, prompts and budgets.

## Static checks

`make lint typecheck` (ruff, mypy strict, ESLint, tsc, Prettier), `make sanitize` (credentials,
account ids, typographic dashes), `make tf-fmt tf-validate tf-lint tf-security`, `make gitleaks`.
