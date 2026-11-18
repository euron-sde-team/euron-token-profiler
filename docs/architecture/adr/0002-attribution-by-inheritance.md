# 0002: Cost is attributed by inheriting agent and tool names down the span tree

Status: accepted

## Context

"Cost per agent" and "cost per tool" are the questions the product exists to answer, but only a
model call carries tokens. Asking every instrumented call site to repeat its agent and tool names
is fragile, and OpenTelemetry has no such notion between processes.

## Decision

An agent span names its agent, a tool span names its tool, and every span below inherits the
nearest agent and tool above it. Inheritance is resolved at ingest, after the batch is written,
over all spans of the affected traces (so late parents and children are both handled), and stored
on each span as `agent_name` and `tool_name`. A model call inside a tool inside an agent carries
both names.

## Consequences

- Each metered span belongs to exactly one agent and at most one tool, so cost per agent, per tool
  and per model each add up to the project total.
- Tool cost means the cost of model calls made inside the tool (a summariser, an embedding), which
  is how cost shows up in practice. A tool's own latency and error rate come from its tool spans.
- Breakdowns are plain indexed `GROUP BY` queries on `spans`.
- Instrumentation that crosses processes keeps the attribution only if the names are sent on the
  spans; the SDK propagates the agent name through `contextvars` for that reason.
