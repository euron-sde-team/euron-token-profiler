from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from tests.integration.conftest import People
from tests.integration.factories import generation, span, trace_id
from tests.integration.support import Project
from tokenprofiler.services.container import Container


async def seed_traces(project: Project) -> dict[str, str]:
    """Four traces with different shapes: cheap, expensive, failing and slow."""
    ids = {name: trace_id() for name in ("cheap", "dear", "failing", "slow")}
    now = datetime.now(UTC)
    await project.send(
        [
            span(
                ids["cheap"], "faq", kind="agent", span_id="a", started=now - timedelta(minutes=30)
            ),
            generation(
                ids["cheap"],
                model="gpt-4o-mini",
                parent="a",
                started=now - timedelta(minutes=30),
                prompt={"name": "faq", "version": 1},
            ),
            span(
                ids["dear"],
                "research",
                kind="agent",
                span_id="a",
                started=now - timedelta(minutes=20),
            ),
            generation(
                ids["dear"],
                model="claude-sonnet-4-5",
                input_tokens=500_000,
                output_tokens=50_000,
                parent="a",
                started=now - timedelta(minutes=20),
            ),
            span(
                ids["failing"],
                "search",
                kind="tool",
                status="error",
                status_message="timeout",
                started=now - timedelta(minutes=10),
            ),
            span(ids["slow"], "batch", duration_ms=30_000, started=now - timedelta(minutes=5)),
        ],
        [
            {
                "id": ids["cheap"],
                "name": "support.chat",
                "user_id": "alice",
                "session_id": "s1",
                "tags": ["beta"],
            },
            {
                "id": ids["dear"],
                "name": "research.report",
                "user_id": "bob",
                "environment": "staging",
            },
            {"id": ids["failing"], "name": "support.chat", "user_id": "alice", "session_id": "s1"},
        ],
    )
    return ids


async def test_list_filters_sort_and_search(project: Project) -> None:
    ids = await seed_traces(project)
    everything = await project.get("/traces", range="1h")
    assert everything["total"] == 4
    assert everything["items"][0]["id"] == ids["slow"]  # newest first

    async def listed(**params: object) -> list[str]:
        return [t["id"] for t in (await project.get("/traces", range="1h", **params))["items"]]

    assert await listed(status="error") == [ids["failing"]]
    assert await listed(model="claude-sonnet-4-5") == [ids["dear"]]
    assert await listed(agent="faq") == [ids["cheap"]]
    assert await listed(prompt="faq") == [ids["cheap"]]
    assert await listed(tool="search") == [ids["failing"]]
    assert await listed(user_id="alice") == [ids["failing"], ids["cheap"]]
    assert await listed(session_id="s1") == [ids["failing"], ids["cheap"]]
    assert await listed(environment="staging") == [ids["dear"]]
    assert await listed(tag="beta") == [ids["cheap"]]
    assert await listed(q="research") == [ids["dear"]]
    assert await listed(q=ids["slow"][:8]) == [ids["slow"]]
    assert await listed(q="alice") == [ids["failing"], ids["cheap"]]
    assert await listed(min_cost="1") == [ids["dear"]]
    assert await listed(min_duration_ms=10_000) == [ids["slow"]]
    assert (await listed(sort="cost"))[0] == ids["dear"]
    assert (await listed(sort="duration"))[0] == ids["slow"]
    assert (await listed(sort="cost", order="asc"))[-1] == ids["dear"]


async def test_pagination_and_old_traces_leave_the_window(project: Project) -> None:
    now = datetime.now(UTC)
    await project.send(
        [span(trace_id(), f"t{i}", started=now - timedelta(minutes=i + 1)) for i in range(7)]
        + [span(trace_id(), "old", started=now - timedelta(days=3))]
    )
    first = await project.get("/traces", range="24h", limit=3)
    assert (first["total"], first["total_capped"], len(first["items"])) == (7, False, 3)
    last = await project.get("/traces", range="24h", limit=3, offset=6)
    assert len(last["items"]) == 1
    week = await project.get("/traces", range="7d")
    assert week["total"] == 8
    assert (await project.api.get(f"{project.base}/traces", range="nope")).status_code == 422


async def test_facets(project: Project) -> None:
    await seed_traces(project)
    facets = await project.get("/traces/facets")
    assert "gpt-4o-mini" in facets["models"]
    assert "faq" in facets["agents"]
    assert facets["tools"] == ["search"]
    assert set(facets["environments"]) == {"default", "staging"}
    assert facets["tags"] == ["beta"]


async def test_overview_kpis_series_and_cache(
    people: People, project: Project, container: Container
) -> None:
    await seed_traces(project)
    first = await project.get("/metrics/overview", range="24h")
    assert first["cached"] is False
    current = first["current"]
    assert current["traces"] == 4
    assert current["errors"] == 1
    assert current["error_rate"] == 25.0
    assert current["users"] == 2
    assert float(current["cost"]) > 1.5
    assert first["previous"]["traces"] == 0
    assert sum(p["traces"] for p in first["series"]) == 4
    assert first["bucket_seconds"] == 1800
    assert "claude-sonnet-4-5" in first["top_models"]
    second = await project.get("/metrics/overview", range="24h")
    assert second["cached"] is True
    assert second["current"] == first["current"]
    # Another project never sees this project's numbers or cache entries.
    other = await people.admin.ok(await people.admin.post("/projects", {"name": "Other"}))
    empty = await people.admin.ok(
        await people.admin.get(f"/projects/{other['id']}/metrics/overview", range="24h")
    )
    assert empty["current"]["traces"] == 0
    keys = [k async for k in container.redis.scan_iter(f"dash:{project.id}:*")]
    assert keys


async def test_breakdowns_attribute_cost_per_dimension(project: Project) -> None:
    await seed_traces(project)

    async def rows(dimension: str) -> dict[str, dict[str, object]]:
        data = await project.get("/metrics/breakdown", dimension=dimension, range="24h")
        return {r["key"]: r for r in data["items"]}

    models = await rows("model")
    assert models["claude-sonnet-4-5"]["calls"] == 1
    assert float(models["claude-sonnet-4-5"]["cost_share"]) > 0.9  # type: ignore[arg-type]
    agents = await rows("agent")
    assert agents["research"]["calls"] == 1
    assert float(agents["research"]["cost"]) > 1  # type: ignore[arg-type]
    assert agents["faq"]["generations"] == 1
    tools = await rows("tool")
    assert tools["search"]["errors"] == 1
    assert tools["search"]["error_rate"] == 100.0
    prompts = await rows("prompt")
    assert prompts["faq"]["version"] == 1
    bad = await project.api.get(f"{project.base}/metrics/breakdown", dimension="nope")
    assert bad.status_code == 422


async def test_viewers_can_read_dashboards(people: People, project: Project) -> None:
    await seed_traces(project)
    response = await people.viewer.get(f"{project.base}/metrics/overview", range="24h")
    assert response.status_code == 200
    await asyncio.sleep(0)


async def test_a_trace_that_just_arrived_is_in_the_relative_window(project: Project) -> None:
    t = trace_id()
    await project.send([span(t, "now", started=datetime.now(UTC))])
    page = await project.get("/traces", range="1h")
    assert [item["id"] for item in page["items"]] == [t]
