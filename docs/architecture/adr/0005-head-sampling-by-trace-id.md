# 0005: Sampling is decided per trace id, and errors and slow spans override it

Status: accepted

## Context

High-volume applications need to keep only a share of traces. Sampling spans independently would
store half-trees; tail sampling needs buffering the system does not have.

## Decision

A trace is kept when a stable hash of its id (as a fraction) is below the project's sampling rate.
Every span of the trace, in any batch and from any process, gets the same answer. On top of that,
a batch that contains a failing span (when `keep_errors` is on) or a span slower than
`keep_slow_ms` keeps its whole trace.

## Consequences

- Kept traces are complete; raising the rate keeps everything a lower rate kept.
- Failures and outliers, the traces people actually look at, survive aggressive sampling.
- If the failing span arrives in a later batch than the rest of an already dropped trace, only the
  later spans are kept. SDKs send a request's spans in one batch, which makes this rare.
- Dashboards computed from sampled data under-count volume by the sampling rate; the project
  settings say so next to the control.
