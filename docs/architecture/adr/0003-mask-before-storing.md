# 0003: PII is masked and payloads are cut before anything is written

Status: accepted

## Context

Prompts and completions routinely contain personal data and sometimes secrets. A redaction step
applied at read time leaves the raw values in the database, backups, the cache and the archive.

## Decision

Masking runs inside the ingest pipeline, before the first write. Project rules choose built-in
detectors (email, card, SSN, phone, IPv4, API key, JWT) and custom regular expressions; strings
are first cut to a maximum length, then masked. A project can store no payloads at all. Token
estimates and costs are computed from the original payload first, so masking never skews numbers.

## Consequences

- Nothing downstream (queries, exports, the cache, the archive, backups) ever holds a masked value.
- Masking is irreversible: a rule added later does not clean data already stored. Retention bounds
  that exposure.
- Python's `re` cannot enforce a match timeout, so custom patterns are validated when saved
  (length, compilation, no nested repetition), editable by administrators only, and never run on
  unbounded text.
- Each span records how many values were masked, which the UI shows without revealing them.
