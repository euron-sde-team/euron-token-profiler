from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Server
from tokenprofiler_sdk import (
    Prompt,
    PromptVariableError,
    TokenProfiler,
    current_trace_id,
    observe,
    usage_from,
)


def test_a_generation_is_a_complete_trace(
    server: Server, make_client: Callable[..., TokenProfiler]
) -> None:
    profiler = make_client(environment="staging", release="1.2.3")
    with profiler.generation(
        "draft",
        model="gpt-4o",
        input="hi",
        prompt=("answer", 3),
        model_parameters={"temperature": 0},
    ) as call:
        call.update(output="hello", usage={"input": 10, "output": 5, "cached": 2})
    profiler.flush()
    (span,) = server.spans
    assert span["kind"] == "generation"
    assert span["model"] == "gpt-4o"
    assert span["usage"] == {"input": 10, "output": 5, "cached": 2}
    assert span["prompt"] == {"name": "answer", "version": 3}
    assert span["input"] == "hi"
    assert span["output"] == "hello"
    assert span["parent_id"] is None
    assert span["model_parameters"] == {"temperature": 0}
    (trace,) = server.traces
    assert trace["id"] == span["trace_id"]
    assert (trace["environment"], trace["release"], trace["name"]) == ("staging", "1.2.3", "draft")
    assert server.requests[0].headers["authorization"] == "Bearer tp_key"


def test_spans_nest_and_agents_are_inherited(
    server: Server, make_client: Callable[..., TokenProfiler]
) -> None:
    profiler = make_client()
    with profiler.trace("support.chat", user_id="u1", session_id="s1", tags=["beta"]) as trace:
        with profiler.agent("support-agent") as agent:
            with profiler.tool("lookup") as tool:
                with profiler.generation("summarise", model="gpt-4o-mini") as inner:
                    pass
            with profiler.generation("reply", model="gpt-4o") as reply:
                reply.mark_first_token()
    profiler.flush()
    by_name = {s["name"]: s for s in server.spans}
    assert {s["trace_id"] for s in by_name.values()} == {trace.id}
    assert by_name["support-agent"]["parent_id"] is None
    assert by_name["lookup"]["parent_id"] == agent.id
    assert by_name["summarise"]["parent_id"] == tool.id
    assert by_name["reply"]["parent_id"] == agent.id
    assert by_name["summarise"]["agent"] == "support-agent"
    assert by_name["reply"]["agent"] == "support-agent"
    assert "agent" not in by_name["support-agent"]
    assert by_name["reply"]["time_to_first_token_ms"] >= 0
    assert inner.parent_id == tool.id
    (sent,) = server.traces
    assert (sent["user_id"], sent["session_id"], sent["tags"]) == ("u1", "s1", ["beta"])
    assert current_trace_id() is None


def test_exceptions_are_recorded_and_re_raised(
    server: Server, make_client: Callable[..., TokenProfiler]
) -> None:
    profiler = make_client()
    with pytest.raises(ValueError, match="boom"), profiler.tool("flaky"):
        raise ValueError("boom")
    profiler.flush()
    (span,) = server.spans
    assert span["status"] == "error"
    assert "ValueError: boom" in span["status_message"]
    assert span["level"] == "error"


def test_observe_records_arguments_and_results(
    server: Server, make_client: Callable[..., TokenProfiler]
) -> None:
    profiler = make_client()

    @profiler.observe(kind="tool", name="add")
    def add(a: int, b: int = 1) -> int:
        return a + b

    assert add(2, b=3) == 5
    profiler.flush()
    (span,) = server.spans
    assert (span["name"], span["kind"]) == ("add", "tool")
    assert span["input"] == {"a": 2, "b": 3}
    assert span["output"] == 5


async def test_observe_supports_async_and_context_propagates(
    server: Server, make_client: Callable[..., TokenProfiler]
) -> None:
    make_client()

    @observe(kind="agent")
    async def run() -> str:
        await asyncio.sleep(0)
        return await child()

    @observe(kind="tool")
    async def child() -> str:
        return "done"

    assert await run() == "done"
    from tokenprofiler_sdk import get_client

    get_client().flush()
    by_name = {s["name"]: s for s in server.spans}
    assert by_name["child"]["parent_id"] == by_name["run"]["id"]
    assert by_name["child"]["agent"] == "run"


def test_threads_keep_their_own_traces(
    server: Server, make_client: Callable[..., TokenProfiler]
) -> None:
    profiler = make_client()
    ids: list[str] = []

    def work() -> None:
        with profiler.span("job") as span:
            ids.append(span.trace_id)

    threads = [threading.Thread(target=work) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    profiler.flush()
    assert len(set(ids)) == 4
    assert len(server.spans) == 4


def test_transient_failures_are_retried_and_rejections_dropped(
    server: Server, make_client: Callable[..., TokenProfiler]
) -> None:
    profiler = make_client()
    server.statuses = [503, 200]
    with profiler.span("a"):
        pass
    profiler.flush()
    assert len(server.bodies) == 2
    assert profiler.stats["sent"] == 2  # one span and its trace
    server.statuses = [422]
    with profiler.span("b"):
        pass
    profiler.flush()
    assert len(server.bodies) == 3
    assert profiler.stats["failed"] == 2


def test_a_full_queue_drops_instead_of_blocking(
    server: Server, make_client: Callable[..., TokenProfiler]
) -> None:
    gate = threading.Event()

    def slow(request: httpx.Request) -> httpx.Response:
        gate.wait(5)
        return server.handler(request)

    profiler = TokenProfiler(
        "http://api.test",
        "tp_key",
        transport=httpx.MockTransport(slow),
        flush_at=1,
        max_queue=3,
        flush_interval=0.01,
    )
    try:
        for _ in range(40):
            with profiler.span("x"):
                pass
        assert profiler.stats["dropped"] > 0
    finally:
        gate.set()
        profiler.shutdown()


def test_disabled_clients_send_nothing(
    server: Server, make_client: Callable[..., TokenProfiler]
) -> None:
    profiler = make_client(enabled=False)
    with profiler.generation("x", model="m"):
        pass
    assert profiler.flush()
    assert server.requests == []


def test_invalid_kinds_and_fields_fail_loudly(make_client: Callable[..., TokenProfiler]) -> None:
    profiler = make_client()
    with pytest.raises(ValueError, match="unknown span kind"):
        profiler.span("x").__class__(profiler, "x", "nope")
    with pytest.raises(TypeError, match="unknown span field"), profiler.span("x") as span:
        span.update(bogus=1)


def test_prompts_are_fetched_cached_compiled_and_survive_an_outage(
    server: Server, make_client: Callable[..., TokenProfiler]
) -> None:
    server.prompt = {
        "name": "triage",
        "version": 3,
        "template": "Classify {{ message }} for {{user}}",
        "config": {"temperature": 0},
        "labels": ["production"],
    }
    profiler = make_client(prompt_cache_ttl=0.0)
    prompt = profiler.get_prompt("triage")
    assert (prompt.version, prompt.ref, prompt.variables) == (3, ("triage", 3), ["message", "user"])
    assert prompt.compile(message="hi", user="ann", extra="ignored") == "Classify hi for ann"
    with pytest.raises(PromptVariableError, match="user"):
        prompt.compile(message="hi")
    server.prompt = None
    assert profiler.get_prompt("triage").version == 3  # stale copy beats an error
    with pytest.raises(httpx.HTTPStatusError):
        profiler.get_prompt("never-seen")
    cached = make_client(prompt_cache_ttl=60)
    server.prompt = {"name": "p", "version": 1, "template": "t", "config": {}, "labels": []}
    cached.get_prompt("p")
    before = len(server.requests)
    cached.get_prompt("p")
    assert len(server.requests) == before


def test_usage_from_understands_common_clients() -> None:
    assert usage_from({"usage": {"prompt_tokens": 9, "completion_tokens": 4}}) == {
        "input": 9,
        "output": 4,
    }
    assert usage_from(
        {
            "usage": {
                "prompt_tokens": 9,
                "completion_tokens": 4,
                "prompt_tokens_details": {"cached_tokens": 3},
            }
        }
    ) == {"input": 9, "output": 4, "cached": 3}
    assert usage_from(
        {"usage": {"input_tokens": 7, "output_tokens": 2, "cache_read_input_tokens": 5}}
    ) == {
        "input": 7,
        "output": 2,
        "cached": 5,
    }
    assert usage_from({"input_tokens": 1}) == {"input": 1}
    assert usage_from(None) == {}

    class Response:
        class usage:  # noqa: N801
            input_tokens = 3
            output_tokens = 1

    assert usage_from(Response()) == {"input": 3, "output": 1}


def test_prompt_objects_can_be_passed_to_generations(
    server: Server, make_client: Callable[..., TokenProfiler]
) -> None:
    profiler = make_client()
    prompt = Prompt(name="p", version=2, template="x")
    with profiler.generation("g", model="m", prompt=prompt):
        pass
    profiler.flush()
    assert server.spans[0]["prompt"] == {"name": "p", "version": 2}
