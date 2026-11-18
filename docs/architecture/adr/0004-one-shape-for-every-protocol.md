# 0004: Every protocol is converted to one normalised shape

Status: accepted

## Context

Traces arrive from the native SDK protocol, from OpenTelemetry over JSON and from OpenTelemetry
over protobuf (the default of the standard Python, Java and Go exporters). Sampling, pricing,
redaction, attribution and storage must behave identically for all of them.

## Decision

Each adapter turns its payload into `SpanIn` and `TraceIn` (pure dataclasses in
`ingest/types.py`) and nothing else. Protobuf is decoded with `opentelemetry-proto` into the same
dictionary shape the JSON path reads, so there is one OTLP mapping, covering the GenAI semantic
conventions, OpenInference and Traceloop attributes plus a few `tokenprofiler.*` attributes. The
pipeline after the adapter never knows which protocol it was.

## Consequences

- A new protocol is one parser and gets the whole pipeline for free.
- Both OTLP encodings are covered by the same mapping tests; the integration suite sends JSON,
  gzip JSON and protobuf and checks the stored result.
- The OTLP response is the standard one; items the parser cannot use come back as `partialSuccess`
  instead of failing the batch.
