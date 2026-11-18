# 0007: Prices are data, and a span's cost is fixed when it is ingested

Status: accepted

## Context

Providers change prices, customers negotiate their own, and self-hosted models cost GPU time
rather than tokens. Cost numbers are used to set budgets, so they must be explainable and must not
change underneath a report.

## Decision

Prices live in a table: a shared builtin set shipped with each release (46 rows, refreshed at
start without touching edited rows) and per-project overrides that always win. Models match by a
regular expression over a normalised name, longest model name first, so dated snapshots and
provider prefixes price like their family. Cost is computed in `Decimal` at ingest and stored on
the span with its source: `reported` (the caller supplied it), `table`, or `none` (no price, cost
zero, flagged in the UI). Changing a price affects spans ingested afterwards.

## Consequences

- A cost can always be explained from the span: tokens, price row, source.
- Historical numbers are stable; there is no silent repricing. (Repricing past spans would be a
  deliberate, auditable action, not a side effect of an edit.)
- A model nobody priced shows up as zero with a visible marker, never as a wrong guess.
- Overrides cover negotiated rates and self-hosted models without code changes.
