from __future__ import annotations

import base64
import gzip
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from tests.integration.conftest import People
from tests.integration.factories import generation, span, trace_id
from tests.integration.support import Project
from tokenprofiler.services.container import Container


async def test_a_trace_is_priced_attributed_and_totalled(project: Project) -> None:
    t = trace_id()
    root = span(t, "support-agent", kind="agent", span_id="root", duration_ms=3000)
    search = span(t, "vector_search", kind="tool", span_id="tool", parent="root", duration_ms=800)
    embed = generation(
        t, model="text-embedding-3-small", input_tokens=2000, output_tokens=0, parent="tool"
    )
    embed["kind"] = "embedding"
    answer = generation(
        t,
        model="gpt-4o",
        input_tokens=1_000_000,
        output_tokens=500_000,
        parent="root",
        prompt={"name": "answer", "version": 2},
        time_to_first_token_ms=420,
    )
    result = await project.send(
        [root, search, embed, answer], [{"id": t, "name": "support.chat", "user_id": "u1"}]
    )
    assert result["accepted_spans"] == 4
    assert result["accepted_traces"] == 1

    detail = await project.get(f"/traces/{t}")
    trace, spans = detail["trace"], {s["id"]: s for s in detail["spans"]}
    assert trace["name"] == "support.chat"
    assert trace["user_id"] == "u1"
    assert trace["span_count"] == 4
    assert trace["generation_count"] == 2
    assert trace["agents"] == ["support-agent"]
    assert trace["tools"] == ["vector_search"]
    assert trace["prompts"] == ["answer"]
    assert sorted(trace["models"]) == ["gpt-4o", "text-embedding-3-small"]
    # 1M in at 2.50 + 0.5M out at 10 = 7.50, plus 2000 embedding tokens at 0.02 per million.
    assert float(spans[answer["id"]]["total_cost"]) == 7.5
    assert abs(float(trace["total_cost"]) - 7.50004) < 1e-9
    assert trace["total_tokens"] == 1_502_000 + 0
    # Attribution flows down: the embedding is inside the tool, inside the agent.
    assert (spans[embed["id"]]["agent_name"], spans[embed["id"]]["tool_name"]) == (
        "support-agent",
        "vector_search",
    )
    assert spans[answer["id"]]["tool_name"] is None
    assert spans[answer["id"]]["cost_source"] == "table"
    assert trace["duration_ms"] == 3000


async def test_sending_a_span_again_replaces_it_and_totals_follow(project: Project) -> None:
    t = trace_id()
    first = generation(t, input_tokens=1000, output_tokens=100, span_id="g1")
    await project.send([first])
    second = generation(t, input_tokens=2000, output_tokens=100, span_id="g1")
    await project.send([second])
    await project.send([generation(t, span_id="g2")])
    detail = await project.get(f"/traces/{t}")
    assert detail["trace"]["span_count"] == 2
    assert detail["trace"]["input_tokens"] == 3000


async def test_missing_usage_is_estimated(project: Project) -> None:
    t = trace_id()
    call = span(t, "llm", kind="generation", model="gpt-4o", input="x" * 4000, output="y" * 400)
    await project.send([call])
    s = (await project.get(f"/traces/{t}"))["spans"][0]
    assert (s["input_tokens"], s["output_tokens"]) == (1000, 100)
    assert s["usage_estimated"] is True
    assert float(s["total_cost"]) > 0


async def test_unpriced_models_are_zero_and_marked(project: Project) -> None:
    t = trace_id()
    await project.send([generation(t, model="my-private-model")])
    s = (await project.get(f"/traces/{t}"))["spans"][0]
    assert s["cost_source"] == "none"
    assert float(s["total_cost"]) == 0


async def test_pii_is_redacted_before_storage(people: People, project: Project) -> None:
    await people.admin.ok(
        await people.admin.patch(
            project.base,
            {
                "redaction": {
                    "custom": [
                        {
                            "name": "emp",
                            "pattern": r"EMP-\d{6}",
                            "replacement": "[REDACTED:employee]",
                        }
                    ],
                    "max_payload_chars": 300,
                }
            },
        )
    )
    t = trace_id()
    result = await project.send(
        [
            span(
                t,
                "chat",
                input={
                    "message": "I am ann@example.com, employee EMP-123456, card 4111 1111 1111 1111"
                },
                output="x" * 1000,
                metadata={"contact": "bob@example.com"},
            )
        ]
    )
    assert result["redactions"] == 4
    s = (await project.get(f"/traces/{t}"))["spans"][0]
    assert "ann@example.com" not in s["input"]
    assert "EMP-123456" not in s["input"]
    assert "[REDACTED:employee]" in s["input"]
    assert "[REDACTED:credit_card]" in s["input"]
    assert s["metadata"] == {"contact": "[REDACTED:email]"}
    assert s["output"].endswith("...[truncated]")
    assert s["redactions"] == 4
    row = await project.get(f"/traces/{t}")
    assert "ann@example.com" not in json.dumps(row)


async def test_payload_storage_can_be_switched_off(people: People, project: Project) -> None:
    await people.admin.ok(
        await people.admin.patch(project.base, {"redaction": {"store_payloads": False}})
    )
    t = trace_id()
    await project.send([span(t, "chat", input="secret", output="secret")])
    s = (await project.get(f"/traces/{t}"))["spans"][0]
    assert s["input"] is None
    assert s["output"] is None


async def test_sampling_keeps_errors_and_slow_spans(people: People, project: Project) -> None:
    await people.admin.ok(
        await people.admin.patch(project.base, {"sampling_rate": 0, "keep_slow_ms": 5000})
    )
    plain, failed, slow = trace_id(), trace_id(), trace_id()
    result = await project.send(
        [
            span(plain, "ok"),
            span(failed, "bad", status="error", status_message="boom"),
            span(slow, "slow", duration_ms=9000),
        ]
    )
    assert result["accepted_traces"] == 2
    assert result["sampled_out_traces"] == 1
    assert (await people.admin.get(f"{project.base}/traces/{plain}")).status_code == 404
    assert (await people.admin.get(f"{project.base}/traces/{failed}")).status_code == 200
    page = await project.get("/traces", range="1h")
    assert page["total"] == 2


async def test_bad_items_are_reported_not_fatal(project: Project) -> None:
    t = trace_id()
    result = await project.send([span(t, "good"), {"id": "x", "trace_id": t, "name": ""}])
    assert result["accepted_spans"] == 1
    assert len(result["rejected"]) == 1


async def test_prompt_versions_seen_in_traces_are_registered(project: Project) -> None:
    t = trace_id()
    await project.send([generation(t, prompt={"name": "seen-in-traces", "version": 4})])
    detail = await project.get("/prompts/seen-in-traces")
    assert [v["version"] for v in detail["versions"]] == [4]
    assert detail["versions"][0]["managed"] is False
    assert detail["versions"][0]["usage"]["calls"] == 1


async def test_keys_are_required_and_limited(
    project: Project, http: httpx.AsyncClient, container: Container, monkeypatch: Any
) -> None:
    missing = await http.post("/v1/ingest", json={})
    assert missing.status_code == 401
    wrong = await http.post("/v1/ingest", json={}, headers={"authorization": "Bearer tp_nope"})
    assert wrong.status_code == 401
    via_header = await http.post("/v1/ingest", json={}, headers={"x-api-key": project.key})
    assert via_header.status_code == 200
    monkeypatch.setattr(
        container, "settings", container.settings.model_copy(update={"ingest_rate_limit": 2})
    )
    codes = [
        (await http.post("/v1/ingest", json={}, headers={"x-api-key": project.key})).status_code
        for _ in range(4)
    ]
    assert codes[-1] == 429
    # A session token is not a key.
    assert (
        await http.get("/api/v1/projects", headers={"authorization": f"Bearer {project.key}"})
    ).status_code == 403


def otlp_body(trace: str) -> dict[str, Any]:
    now = datetime.now(UTC) - timedelta(minutes=2)
    nanos = int(now.timestamp() * 1e9)

    def kv(key: str, **v: Any) -> dict[str, Any]:
        return {"key": key, "value": v}

    return {
        "resourceSpans": [
            {
                "resource": {"attributes": [kv("service.name", stringValue="svc")]},
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": trace,
                                "spanId": "00000000000000a1",
                                "name": "agent run",
                                "startTimeUnixNano": str(nanos),
                                "endTimeUnixNano": str(nanos + 2_000_000_000),
                                "attributes": [
                                    kv("gen_ai.operation.name", stringValue="invoke_agent"),
                                    kv("gen_ai.agent.name", stringValue="otel-agent"),
                                ],
                            },
                            {
                                "traceId": trace,
                                "spanId": "00000000000000a2",
                                "parentSpanId": "00000000000000a1",
                                "name": "chat",
                                "startTimeUnixNano": str(nanos + 100_000_000),
                                "endTimeUnixNano": str(nanos + 900_000_000),
                                "attributes": [
                                    kv("gen_ai.operation.name", stringValue="chat"),
                                    kv("gen_ai.request.model", stringValue="claude-sonnet-4-5"),
                                    kv("gen_ai.usage.input_tokens", intValue="1000000"),
                                    kv("gen_ai.usage.output_tokens", intValue="100000"),
                                ],
                            },
                        ]
                    }
                ],
            }
        ]
    }


async def test_otlp_json_with_gzip(project: Project, http: httpx.AsyncClient) -> None:
    t = "ab" * 16
    body = gzip.compress(json.dumps(otlp_body(t)).encode())
    response = await http.post(
        "/v1/otlp/v1/traces",
        content=body,
        headers={
            "authorization": f"Bearer {project.key}",
            "content-type": "application/json",
            "content-encoding": "gzip",
        },
    )
    assert response.status_code == 200, response.text
    detail = await project.get(f"/traces/{t}")
    assert detail["trace"]["agents"] == ["otel-agent"]
    chat = next(s for s in detail["spans"] if s["name"] == "chat")
    assert chat["agent_name"] == "otel-agent"
    # 1M in at 3.00 + 0.1M out at 15.00
    assert float(chat["total_cost"]) == 4.5


async def test_otlp_protobuf(project: Project, http: httpx.AsyncClient) -> None:
    from google.protobuf.json_format import ParseDict
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

    t = "cd" * 16
    body = otlp_body(t)
    for raw in body["resourceSpans"][0]["scopeSpans"][0]["spans"]:
        # The protobuf JSON mapping carries ids as base64 bytes.
        for key in ("traceId", "spanId", "parentSpanId"):
            if key in raw:
                raw[key] = base64.b64encode(bytes.fromhex(raw[key])).decode()
    message = ParseDict(body, ExportTraceServiceRequest())
    response = await http.post(
        "/v1/otlp/v1/traces",
        content=message.SerializeToString(),
        headers={
            "authorization": f"Bearer {project.key}",
            "content-type": "application/x-protobuf",
        },
    )
    assert response.status_code == 200, response.text
    detail = await project.get(f"/traces/{t}")
    assert detail["trace"]["span_count"] == 2
    assert detail["trace"]["models"] == ["claude-sonnet-4-5"]


async def test_otlp_rejects_bad_bodies(project: Project, http: httpx.AsyncClient) -> None:
    headers = {"authorization": f"Bearer {project.key}"}
    bad_json = await http.post(
        "/v1/otlp/v1/traces", content=b"{", headers=headers | {"content-type": "application/json"}
    )
    assert bad_json.status_code == 422
    bad_type = await http.post(
        "/v1/otlp/v1/traces", content=b"x", headers=headers | {"content-type": "text/plain"}
    )
    assert bad_type.status_code == 415
    bomb = gzip.compress(b"0" * 2_000_000)
    ok = await http.post(
        "/v1/otlp/v1/traces",
        content=bomb,
        headers=headers | {"content-type": "application/json", "content-encoding": "gzip"},
    )
    assert ok.status_code == 422
    partial = await http.post(
        "/v1/otlp/v1/traces",
        json={"resourceSpans": [{"scopeSpans": [{"spans": [{"name": "no ids"}]}]}]},
        headers=headers,
    )
    assert partial.status_code == 200
    assert partial.json()["partialSuccess"]["rejectedSpans"] == 1
