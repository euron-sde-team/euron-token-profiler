# Threat model (STRIDE)

Assets: stored prompts and completions (may hold personal data), project API keys, sessions, the
price and budget configuration, the cost numbers people act on. Trust boundaries: the internet to
the load balancer; browsers to the API; SDKs and exporters to the ingest endpoints; the API and
worker to PostgreSQL, Valkey, S3 and (outbound) customer webhooks.

| Threat | Example | Mitigation |
| ------ | ------- | ---------- |
| **S**poofing | Replaying a stolen project key | Keys are revocable, rate limited, never shown again; only an HMAC is stored |
| | Guessing a login | Argon2id, per-address and per-account limits, lockout, equal timing for unknown emails |
| | Forged `X-Forwarded-For` to dodge limits | Trusted proxy range only (VPC CIDR), never `*` |
| **T**ampering | Cross-site request with the session cookie | SameSite=Lax cookie and an origin check on unsafe methods |
| | Editing another project's data by id | Every query is scoped by `project_id`; the project comes from the path or the key, not the body |
| | A traces batch overwriting another project's spans | Primary keys lead with `project_id`; upserts are per project |
| **R**epudiation | "Who changed the retention?" | Audit events with actor, action and target |
| **I**nformation disclosure | PII in prompts stored forever | Masking before storage, optional no-payload mode, retention, encrypted archive |
| | One project reading another's cached dashboard | Cache keys contain the project id |
| | Secrets in logs | Log redaction of known secret fields; keys are never logged; webhook URLs sealed |
| | Webhook URL leaks a token | Sealed with AES-GCM bound to the project; never returned |
| **D**enial of service | Oversized or compressed bodies | Body, decompressed and batch limits; bounded inflater |
| | Catastrophic regular expressions | Pattern checks on save, payload length cap before any rule runs, administrators only |
| | A noisy SDK floods the database | Per-key rate limit with `Retry-After`; sampling; batch writes |
| | Expensive dashboard queries | Partial indexes, bounded counts, 30 second aggregate cache |
| | Retention deleting a huge backlog in one transaction | Small batches, one transaction each |
| **E**levation of privilege | A viewer calls a write endpoint | Server-side role dependencies on every write route; the UI only hides controls |
| | A key used as a session | Keys are refused by the control plane (`api_key_not_allowed`) and sessions by ingest |
| | SSRF through the alert webhook | Public addresses only, validated on save and delivery, no redirects |
| | Role change not taking effect | Role changes bump `session_version`, ending sessions at once |

Residual risks: masking is pattern based and can miss unusual formats; Python regular expressions
cannot be bounded in time, so custom patterns are an administrator-only privilege; a project key in
a client-side application is public by nature, so use keys in servers only; people see all projects
in a deployment.
