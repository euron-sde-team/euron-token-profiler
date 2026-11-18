# Security model

## Who can do what

| Actor            | Credential                          | Can                                                         |
| ---------------- | ----------------------------------- | ----------------------------------------------------------- |
| Viewer           | session                             | read projects, traces, dashboards, prompts, prices, budgets |
| Member           | session                             | viewer, plus prompts, prices, budgets, rules, keys, redaction preview |
| Admin            | session                             | member, plus people, projects, privacy, retention, webhook, archives, audit |
| SDK or exporter  | project API key (`tp_...`)          | send traces to one project, fetch its prompts, nothing else |
| Worker           | database and Valkey access          | evaluate alerts, enforce retention, write the archive       |

People see every project; projects are a data boundary for keys, not an access-control boundary.
Add a deployment per tenant when tenants must not see each other.

## Passwords and sessions

- Argon2id (time 3, 64 MiB, parallelism 2), hashed off the event loop. Unknown emails verify against
  a dummy hash so timing does not reveal accounts. Eight failures lock an account for 15 minutes;
  sign-in is also limited per address (10 a minute).
- Sessions are HS256 JWTs (issuer and audience pinned) in an httpOnly, SameSite=Lax cookie (Secure
  in production). They carry the user's `session_version`; a password change or a role change bumps
  it, which signs the person out everywhere. Logout denylists the token id in Valkey until it
  expires. Passwords must be 10 to 256 characters and not trivially weak.
- Cookie-authenticated unsafe requests are accepted only from the configured web origin (CSRF).

## Project API keys

`tp_<prefix>_<secret>`: a 10 character prefix finds the row, a 256-bit secret proves possession.
Only `HMAC-SHA256(secret, pepper)` is stored, so a database copy alone cannot be replayed. Keys are
revocable at once, show only a prefix in the UI, and are rate limited per key (default 1,200
requests a minute, `429` with `Retry-After`). A key can be sent as a bearer token or `x-api-key`.

## Data at rest

- The webhook URL is sealed with AES-256-GCM under a key derived (HKDF) from `ENCRYPTION_KEY`, bound
  to the project id, and never returned by the API.
- On AWS, RDS and ElastiCache use the deployment KMS key; the archive bucket enforces TLS, blocks
  public access and encrypts with SSE-KMS.
- Secrets (`SESSION_SECRET`, `API_KEY_PEPPER`, `ENCRYPTION_KEY`) are required, at least 32
  characters and all different in production; the process refuses to start otherwise
  (`Settings.production_problems`).

## Privacy of traces

Masking happens before storage, so removed values never reach the database, the cache or the
archive. Built-in detectors cover email, card numbers (Luhn verified), US SSNs, phone numbers,
IPv4, API keys and tokens, and JWTs; custom regular expressions cover the rest. A project can store
no payloads at all. Payloads are cut to a configured length. Masking is best effort: tell your
team what is sent, and prefer not sending secrets over relying on a pattern.

## Network and input handling

- Request bodies are limited (16 MB), decompressed OTLP bodies are limited (64 MB) with a bounded
  inflater, and batches are limited (5,000 items). Items are validated individually.
- Webhooks (SSRF): http and https only, every resolved address must be public unless explicitly
  allowed for development, checked on save and again on delivery, no redirects, short timeout.
- Custom regular expressions are rejected when too long, invalid or built from nested repetition.
- CORS lists explicit origins; HSTS is sent in production; `X-Request-Id` is on every response.
- Uvicorn trusts `X-Forwarded-For` only from the VPC range.
- `/metrics` is not routed by the load balancer.

## Auditing

Project, key, prompt, price, budget, rule and people changes write an audit event with the actor and
a summary of the change (never secrets). Administrators read them under Settings, Activity.

## Dependencies and supply chain

Base images and tools are pinned. CI runs gitleaks, ruff, mypy (strict), ESLint, tsc, Terraform
validation, tflint and checkov. `make sanitize` blocks credentials, account ids and typographic
dashes from being committed.
