from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.integration.conftest import People
from tests.integration.factories import generation, trace_id
from tests.integration.support import Project


async def test_prompt_versions_labels_and_fetch(people: People, project: Project) -> None:
    api = people.member

    async def save(template: str, labels: list[str] | None = None) -> int:
        body = {"name": "support-triage", "template": template, "labels": labels or []}
        return int((await api.ok(await api.post(f"{project.base}/prompts", body)))["version"])

    assert await save("v1 {{message}}", ["production"]) == 1
    assert await save("v2 {{message}}") == 2
    assert await save("v3 {{message}}", ["staging"]) == 3

    detail = await project.get("/prompts/support-triage")
    labels = {v["version"]: v["labels"] for v in detail["versions"]}
    assert labels == {1: ["production"], 2: [], 3: ["staging"]}

    headers = {"authorization": f"Bearer {project.key}"}

    async def fetch(**params: object) -> dict[str, object]:
        response = await project.http.get(
            "/v1/prompts/support-triage", params=params, headers=headers
        )
        assert response.status_code == 200, response.text
        return dict(response.json())

    assert (await fetch())["version"] == 1  # production by default
    assert (await fetch(label="staging"))["version"] == 3
    assert (await fetch(version=2))["template"] == "v2 {{message}}"

    await api.ok(
        await api.request(
            "PUT",
            f"{project.base}/prompts/support-triage/label",
            json={"label": "production", "version": 3},
        )
    )
    assert (await fetch())["version"] == 3
    labels_now = {
        v["version"]: v["labels"]
        for v in (await project.get("/prompts/support-triage"))["versions"]
    }
    assert labels_now[1] == []
    assert labels_now[3] == ["production", "staging"] or labels_now[3] == ["staging", "production"]

    missing = await project.http.get("/v1/prompts/none", headers=headers)
    assert missing.status_code == 404
    assert (
        await people.viewer.post(f"{project.base}/prompts", {"name": "x", "template": "t"})
    ).status_code == 403


async def test_prompt_usage_and_cost_per_version(project: Project) -> None:
    now = datetime.now(UTC)
    spans = []
    for i, version in enumerate((1, 1, 2)):
        t = trace_id()
        spans.append(
            generation(
                t,
                model="gpt-4o",
                input_tokens=1_000_000,
                output_tokens=0,
                started=now - timedelta(minutes=i + 1),
                prompt={"name": "answer", "version": version},
            )
        )
    await project.send(spans)
    listing = await project.get("/prompts", range="24h")
    row = next(p for p in listing["items"] if p["name"] == "answer")
    assert row["latest_version"] == 2
    assert row["versions"] == 2
    assert row["usage"]["calls"] == 3
    assert float(row["usage"]["cost"]) == 7.5
    detail = await project.get("/prompts/answer", range="24h")
    by_version = {v["version"]: v["usage"] for v in detail["versions"]}
    assert by_version[1]["calls"] == 2
    assert float(by_version[1]["cost"]) == 5.0
    assert by_version[2]["calls"] == 1


async def test_price_overrides_change_cost_for_new_spans(people: People, project: Project) -> None:
    api = people.member
    table = await project.get("/prices")
    assert any(row["scope"] == "shared" and row["model"] == "gpt-4o" for row in table)
    lookup = await project.get("/prices/lookup", model="openai/gpt-4o-2024-08-06")
    assert lookup["model"] == "gpt-4o"
    assert float(lookup["input_per_mtok"]) == 2.5

    before = trace_id()
    await project.send([generation(before, input_tokens=1_000_000, output_tokens=0)])
    override = await api.ok(
        await api.request(
            "PUT",
            f"{project.base}/prices",
            json={"model": "gpt-4o", "input_per_mtok": "1.0", "output_per_mtok": "4.0"},
        )
    )
    assert override["scope"] == "project"
    after = trace_id()
    await project.send([generation(after, input_tokens=1_000_000, output_tokens=0)])
    cost_before = float((await project.get(f"/traces/{before}"))["trace"]["total_cost"])
    cost_after = float((await project.get(f"/traces/{after}"))["trace"]["total_cost"])
    assert (cost_before, cost_after) == (
        2.5,
        1.0,
    )  # existing spans keep the price they were billed at

    table = await project.get("/prices")
    shared = next(r for r in table if r["scope"] == "shared" and r["model"] == "gpt-4o")
    assert shared["overridden"] is True
    assert (await project.get("/prices/lookup", model="gpt-4o"))["scope"] == "project"

    assert (
        await people.viewer.request(
            "PUT",
            f"{project.base}/prices",
            json={"model": "x", "input_per_mtok": 1, "output_per_mtok": 1},
        )
    ).status_code == 403
    await api.ok(await api.delete(f"{project.base}/prices/{override['id']}"))
    assert (await project.get("/prices/lookup", model="gpt-4o"))["scope"] == "shared"
    bad = await api.request(
        "PUT",
        f"{project.base}/prices",
        json={"model": "x", "input_per_mtok": 1, "output_per_mtok": 1, "match_pattern": "(a+)+"},
    )
    assert bad.status_code == 422
    nothing = await project.api.get(f"{project.base}/prices/lookup", model="no-such-model")
    assert nothing.status_code == 404
