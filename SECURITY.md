# Security Policy

## Supported versions

| Version            | Supported |
| ------------------ | --------- |
| 0.x (latest minor) | Yes       |
| Older minors       | No        |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately through GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository ("Security" tab, "Report a vulnerability").

Please include:

- the affected component (`apps/api`, `apps/web`, `infra/terraform/...`) and version or commit,
- a description of the issue and its impact,
- steps to reproduce, or a proof of concept,
- any suggested mitigation.

What to expect:

| Stage                                          | Target                                                               |
| ---------------------------------------------- | -------------------------------------------------------------------- |
| Acknowledgement                                | within 3 business days                                               |
| Initial assessment and severity                | within 7 business days                                               |
| Fix or mitigation for critical and high issues | within 30 days                                                       |
| Coordinated public disclosure                  | after a fix is released, credited to you unless you prefer otherwise |

## Scope

In scope: the code in this repository and the infrastructure it provisions with its
default settings. That includes the ingest endpoints (native and OTLP), project API key
handling and rate limits, PII redaction and sampling at ingest, alert webhook delivery
(SSRF guard), the archive store and the web app.

Out of scope:

- **What your application sends.** TokenProfiler stores the traces you ship, after the
  redaction rules you configure; choosing what to instrument and which rules to enable is
  the operator's responsibility.
- **Custom redaction patterns.** Python regular expressions have no match timeout; the
  pattern checks reject common catastrophic shapes but cannot prove every pattern safe.
  Only administrators can save patterns.
- **The demo seed.** `make demo` creates well-known demo accounts on purpose and refuses to
  run with `APP_ENV=production`.
- Findings that require a compromised host, a compromised AWS account or leaked deployment
  secrets.
- Denial of service against a deployment you operate yourself by sending it more work than
  its hardware can serve (that is what the queue limits and rate limits are for).

## Hardening checklist for operators

See [docs/architecture/security.md](docs/architecture/security.md#operator-checklist).
