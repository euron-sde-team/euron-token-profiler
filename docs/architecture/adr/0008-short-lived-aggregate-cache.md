# 0008: Dashboard aggregates are cached in Valkey for a short, fixed time

Status: accepted

## Context

Opening the overview runs several aggregate queries; many people open the same dashboard, and it
refreshes itself every 30 seconds. Per-ingest cache invalidation would make the cache useless
under steady traffic.

## Decision

Overview and breakdown results are cached under `dash:<project>:<kind>:<hash of parameters>` for
`DASHBOARD_CACHE_TTL_S` (30 seconds). Relative ranges end on a 30 second boundary so that viewers
in the same half minute ask for the same window and share one entry. There is no invalidation:
staleness is bounded by the TTL, and responses say when they were computed and whether they came
from the cache.

## Consequences

- Database load from dashboards is bounded by projects times ranges times two requests a minute,
  not by the number of viewers.
- Numbers can be up to 30 seconds old. Trace lists and details are not cached.
- The key contains the project id, so a cache entry can never be served to another project.
- Setting the TTL to 0 disables the cache (used when debugging).
