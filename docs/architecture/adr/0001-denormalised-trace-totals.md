# 0001: Trace totals are denormalised from spans at ingest

Status: accepted

## Context

The trace list, the overview and every filter need a trace's duration, status, tokens, cost and
the models, agents and tools it touched. Computing them from spans on every read means a join and
a group by over the largest table for every page view.

## Decision

Each ingest batch recomputes the totals of the traces it touched with one `UPDATE ... FROM
(SELECT ... GROUP BY trace_id)` and stores them on `traces`, including the distinct model, agent,
tool and prompt names as GIN-indexed arrays. Reads of the list, the filters and the overview use
only `traces`. Breakdowns that need per-span detail read `spans` through partial indexes.

## Consequences

- The hot reads touch a narrow table with a handful of indexes; filters by model, agent, tool or
  prompt never join.
- A write does a bit more work. The recompute is bounded by the batch (1,000 traces per
  statement) and runs in the same transaction, so totals are never stale or half applied.
- Two batches of one trace could race, so each batch takes advisory locks over its trace ids
  (sorted, to avoid deadlocks) before writing.
- Totals count metered spans only (generations and embeddings), which also prevents a parent
  agent span that reports an aggregate usage from double counting.
