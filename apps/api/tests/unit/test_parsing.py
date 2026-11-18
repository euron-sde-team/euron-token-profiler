from __future__ import annotations

import base64
from typing import Any

from tokenprofiler.ingest.native import parse_native
from tokenprofiler.ingest.otlp import any_value, attributes, parse_otlp
from tokenprofiler.schemas.ingest import IngestBatch

TRACE = "5b8efff798038103d269b633813fc60c"
ROOT = "eee19b7ec3c1b174"
CHILD = "eee19b7ec3c1b175"


def kv(key: str, **value: Any) -> dict[str, Any]:
    return {"key": key, "value": value}


def otlp_document() -> dict[str, Any]:
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        kv("service.name", stringValue="support-api"),
                        kv("deployment.environment", stringValue="production"),
                        kv("service.version", stringValue="1.4.2"),
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": TRACE,
                                "spanId": ROOT,
                                "parentSpanId": "",
                                "name": "support-agent",
                                "startTimeUnixNano": "1700000000000000000",
                                "endTimeUnixNano": "1700000002000000000",
                                "attributes": [
                                    kv("gen_ai.operation.name", stringValue="invoke_agent"),
                                    kv("gen_ai.agent.name", stringValue="support-agent"),
                                    kv("user.id", stringValue="usr_1"),
                                ],
                                "status": {"code": 1},
                            },
                            {
                                "traceId": TRACE,
                                "spanId": CHILD,
                                "parentSpanId": ROOT,
                                "name": "chat gpt-4o",
                                "startTimeUnixNano": "1700000000500000000",
                                "endTimeUnixNano": "1700000001500000000",
                                "attributes": [
                                    kv("gen_ai.operation.name", stringValue="chat"),
                                    kv("gen_ai.system", stringValue="openai"),
                                    kv("gen_ai.request.model", stringValue="gpt-4o"),
                                    kv("gen_ai.response.model", stringValue="gpt-4o-2024-08-06"),
                                    kv("gen_ai.usage.input_tokens", intValue="1200"),
                                    kv("gen_ai.usage.output_tokens", intValue="80"),
                                    kv("gen_ai.request.temperature", doubleValue=0.2),
                                    kv("tokenprofiler.prompt.name", stringValue="triage"),
                                    kv("tokenprofiler.prompt.version", intValue="3"),
                                    kv("gen_ai.prompt", stringValue='[{"role": "user"}]'),
                                ],
                                "events": [
                                    {
                                        "name": "exception",
                                        "attributes": [kv("exception.message", stringValue="boom")],
                                    }
                                ],
                                "status": {"code": 2, "message": "failed"},
                            },
                            {"traceId": "", "spanId": "", "name": "broken"},
                        ]
                    }
                ],
            }
        ]
    }


def test_any_value_decoding() -> None:
    assert any_value({"intValue": "7"}) == 7
    assert any_value({"boolValue": True}) is True
    assert any_value({"arrayValue": {"values": [{"stringValue": "a"}, {"intValue": "2"}]}}) == [
        "a",
        2,
    ]
    assert any_value({"kvlistValue": {"values": [kv("k", stringValue="v")]}}) == {"k": "v"}
    assert attributes([kv("a", intValue="1")]) == {"a": 1}


def test_otlp_json_maps_genai_conventions() -> None:
    batch = parse_otlp(otlp_document())
    assert len(batch.spans) == 2
    assert len(batch.rejected) == 1
    agent, call = sorted(batch.spans, key=lambda s: s.started_at)
    assert agent.kind == "agent"
    assert agent.agent_name == "support-agent"
    assert agent.parent_id is None
    assert agent.trace_name == "support-agent"
    assert agent.user_id == "usr_1"
    assert agent.environment == "production"
    assert agent.release == "1.4.2"
    assert agent.metadata["service"] == "support-api"
    assert call.kind == "generation"
    assert call.model == "gpt-4o-2024-08-06"
    assert call.provider == "openai"
    assert (call.input_tokens, call.output_tokens) == (1200, 80)
    assert call.prompt_name == "triage"
    assert call.prompt_version == 3
    assert call.status == "error"
    assert call.status_message == "failed"
    assert call.input == [{"role": "user"}]
    assert call.parent_id == ROOT
    assert (call.ended_at - call.started_at).total_seconds() == 1.0
    assert call.model_parameters == {"temperature": 0.2}


def test_otlp_protobuf_ids_are_base64() -> None:
    doc = otlp_document()
    span = doc["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    span["traceId"] = base64.b64encode(bytes.fromhex(TRACE)).decode()
    span["spanId"] = base64.b64encode(bytes.fromhex(ROOT)).decode()
    batch = parse_otlp(doc, base64_ids=True)
    ids = {s.trace_id for s in batch.spans}
    assert TRACE in ids


def test_openinference_and_traceloop_kinds() -> None:
    doc = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": TRACE,
                                "spanId": ROOT,
                                "name": "retrieve",
                                "startTimeUnixNano": "1",
                                "endTimeUnixNano": "2",
                                "attributes": [
                                    kv("openinference.span.kind", stringValue="RETRIEVER")
                                ],
                            },
                            {
                                "traceId": TRACE,
                                "spanId": CHILD,
                                "name": "llm",
                                "startTimeUnixNano": "1",
                                "endTimeUnixNano": "2",
                                "attributes": [
                                    kv("llm.model_name", stringValue="gpt-4o"),
                                    kv("llm.token_count.prompt", intValue="5"),
                                    kv("llm.token_count.completion", intValue="6"),
                                ],
                            },
                        ]
                    }
                ]
            }
        ]
    }
    kinds = {s.span_id: s.kind for s in parse_otlp(doc).spans}
    assert kinds == {ROOT: "retriever", CHILD: "generation"}


def test_native_items_are_validated_one_by_one() -> None:
    batch = parse_native(
        IngestBatch(
            spans=[
                {
                    "id": "s1",
                    "trace_id": "t1",
                    "name": "call",
                    "kind": "generation",
                    "start_time": "2026-11-01T10:00:00Z",
                    "end_time": "2026-11-01T10:00:02Z",
                    "model": "gpt-4o",
                    "usage": {"input": 10, "output": 5, "cached": 2},
                    "prompt": {"name": "p", "version": 2},
                    "agent": "a",
                },
                {
                    "id": "bad id!",
                    "trace_id": "t1",
                    "name": "x",
                    "start_time": "2026-11-01T10:00:00Z",
                },
                {"id": "s3", "trace_id": "t1", "name": "x", "start_time": "nonsense"},
            ],
            traces=[{"id": "t1", "name": "chat", "tags": ["a", "a", "b"]}, {"name": "no id"}],
        )
    )
    assert len(batch.spans) == 1
    assert len(batch.traces) == 1
    assert len(batch.rejected) == 3
    span = batch.spans[0]
    assert span.cached_tokens == 2
    assert span.prompt_version == 2
    assert span.agent_name == "a"
    assert batch.traces[0].tags == ["a", "b"]


def test_native_end_before_start_is_clamped() -> None:
    batch = parse_native(
        IngestBatch(
            spans=[
                {
                    "id": "s1",
                    "trace_id": "t1",
                    "name": "x",
                    "start_time": "2026-11-01T10:00:05Z",
                    "end_time": "2026-11-01T10:00:01Z",
                }
            ]
        )
    )
    assert batch.spans[0].ended_at == batch.spans[0].started_at
