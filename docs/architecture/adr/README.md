# Architecture decision records

Short records of the decisions that shape TokenProfiler, each with its context and trade-offs.

| ADR                                                          | Decision                                                                 |
| ------------------------------------------------------------ | ------------------------------------------------------------------------ |
| [0001](0001-denormalised-trace-totals.md)                    | Trace totals are denormalised from spans at ingest                       |
| [0002](0002-attribution-by-inheritance.md)                   | Cost is attributed by inheriting agent and tool names down the span tree |
| [0003](0003-mask-before-storing.md)                          | PII is masked and payloads are cut before anything is written            |
| [0004](0004-one-shape-for-every-protocol.md)                 | Every protocol is converted to one normalised shape                      |
| [0005](0005-head-sampling-by-trace-id.md)                    | Sampling is decided per trace id; errors and slow spans override it      |
| [0006](0006-floci-for-local-aws.md)                          | Floci emulates AWS locally, provisioned by the production Terraform      |
| [0007](0007-prices-are-data-and-cost-is-fixed-at-ingest.md)  | Prices are data, and a span's cost is fixed when it is ingested          |
| [0008](0008-short-lived-aggregate-cache.md)                  | Dashboard aggregates are cached in Valkey for a short, fixed time        |
