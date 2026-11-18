from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from tests.integration.conftest import People
from tests.integration.factories import generation, span, trace_id
from tests.integration.support import Project
from tokenprofiler.repositories.projects import ProjectRepository
from tokenprofiler.services.alerts import AlertService
from tokenprofiler.services.container import Container


async def evaluate(container: Container, project: Project) -> int:
    async with container.db.session() as session:
        row = await ProjectRepository(session).get(uuid.UUID(project.id))
        assert row is not None
        return await AlertService(container, session).evaluate_project(row)


async def events(project: Project, **params: Any) -> list[dict[str, Any]]:
    page = await project.get("/alert-events", **params)
    return list(page["items"])


async def test_budget_states_events_and_resolution(
    people: People, project: Project, container: Container
) -> None:
    api = people.member
    await project.send([generation(trace_id(), input_tokens=1_000_000, output_tokens=0)])  # $2.50
    created = await api.ok(
        await api.post(
            f"{project.base}/budgets",
            {
                "name": "Daily",
                "scope": "project",
                "period": "day",
                "limit_usd": "10",
                "warn_at_percent": 20,
            },
        )
    )
    assert created["state"] == "warning"
    assert created["percent_used"] == 25.0
    assert await evaluate(container, project) == 1
    assert await evaluate(container, project) == 0  # nothing new: no duplicate event
    firing = await events(project, firing_only="true")
    assert len(firing) == 1
    assert (firing[0]["severity"], firing[0]["kind"]) == ("warning", "budget")

    await project.send(
        [generation(trace_id(), input_tokens=4_000_000, output_tokens=0)]
    )  # now $12.50
    assert await evaluate(container, project) == 1  # escalated, same event
    firing = await events(project, firing_only="true")
    assert len(firing) == 1
    assert firing[0]["severity"] == "critical"
    overview = await project.get("/alerts")
    assert overview["firing"] == 1
    assert overview["budgets"][0]["state"] == "exceeded"

    await api.ok(
        await api.request(
            "PUT",
            f"{project.base}/budgets/{created['id']}",
            json={"name": "Daily", "scope": "project", "period": "day", "limit_usd": "1000"},
        )
    )
    assert await evaluate(container, project) == 1
    assert await events(project, firing_only="true") == []
    history = await events(project)
    assert [e["state"] for e in history] == ["resolved"]
    assert history[0]["resolved_at"] is not None


async def test_scoped_budgets_count_only_their_scope(
    people: People, project: Project, container: Container
) -> None:
    api = people.member
    t = trace_id()
    await project.send(
        [
            span(t, "a", kind="agent", span_id="a"),
            generation(t, parent="a", model="gpt-4o", input_tokens=1_000_000, output_tokens=0),
            generation(t, model="gpt-4o-mini", input_tokens=1_000_000, output_tokens=0),
        ]
    )
    for scope, value in (("model", "gpt-4o"), ("agent", "a"), ("model", "gpt-4o-mini")):
        await api.ok(
            await api.post(
                f"{project.base}/budgets",
                {
                    "name": f"{scope} {value}",
                    "scope": scope,
                    "scope_value": value,
                    "period": "month",
                    "limit_usd": "100",
                },
            )
        )
    spend = {
        b["scope_value"]: float(b["spent_usd"]) for b in (await project.get("/alerts"))["budgets"]
    }
    assert spend == {"gpt-4o": 2.5, "a": 2.5, "gpt-4o-mini": 0.15}
    bad = await api.post(
        f"{project.base}/budgets", {"name": "x", "scope": "model", "limit_usd": "1"}
    )
    assert bad.status_code == 422


async def test_rules_fire_and_resolve_and_notify_the_webhook(
    people: People, project: Project, container: Container, monkeypatch: Any
) -> None:
    delivered: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        delivered.append(json.loads(request.content))
        return httpx.Response(204)

    monkeypatch.setattr(
        container, "http", httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    await people.admin.ok(
        await people.admin.patch(
            project.base, {"webhook_url": "http://hooks.example.com/token-abc"}
        )
    )
    now = datetime.now(UTC)
    await project.send(
        [
            span(trace_id(), "x", status="error", started=now - timedelta(minutes=i + 1))
            for i in range(6)
        ]
        + [span(trace_id(), "ok", started=now - timedelta(minutes=10 + i)) for i in range(6)]
    )
    rule = await people.member.ok(
        await people.member.post(
            f"{project.base}/alert-rules",
            {
                "name": "Errors",
                "metric": "error_rate",
                "threshold": "20",
                "window_minutes": 60,
                "min_traces": 10,
                "severity": "critical",
            },
        )
    )
    assert await evaluate(container, project) == 1
    assert delivered[0]["event"] == "alert.firing"
    assert delivered[0]["alert"]["name"] == "Errors"
    assert delivered[0]["project"]["slug"] == project.slug
    firing = await events(project, firing_only="true")
    assert firing[0]["notified_at"] is not None
    assert float(firing[0]["value"]) == 50.0

    # Not enough traces in a tiny window means no data, not an alert: the event resolves.
    await people.member.ok(
        await people.member.request(
            "PUT",
            f"{project.base}/alert-rules/{rule['id']}",
            json={
                "name": "Errors",
                "metric": "error_rate",
                "threshold": "20",
                "window_minutes": 60,
                "min_traces": 500,
            },
        )
    )
    assert await evaluate(container, project) == 1
    assert delivered[-1]["event"] == "alert.resolved"
    assert await events(project, firing_only="true") == []


async def test_silence_rule_and_blocked_webhooks(
    people: People, project: Project, container: Container
) -> None:
    await people.member.ok(
        await people.member.post(
            f"{project.base}/alert-rules",
            {
                "name": "Silence",
                "metric": "trace_count",
                "comparator": "below",
                "threshold": "1",
                "window_minutes": 30,
                "min_traces": 0,
            },
        )
    )
    assert await evaluate(container, project) == 1
    assert (await events(project, firing_only="true"))[0]["kind"] == "rule"
    await project.send([span(trace_id(), "alive")])
    assert await evaluate(container, project) == 1
    assert await events(project, firing_only="true") == []


async def test_webhook_ssrf_guard_when_private_hosts_are_off(
    people: People, project: Project, container: Container, monkeypatch: Any
) -> None:
    strict = container.settings.model_copy(update={"webhook_allow_private_hosts": False})
    monkeypatch.setattr(container, "settings", strict)
    for url in (
        "http://127.0.0.1:9/x",
        "http://169.254.169.254/latest/meta-data",
        "http://localhost/hook",
    ):
        response = await people.admin.patch(project.base, {"webhook_url": url})
        assert response.status_code == 422, url
        assert response.json()["error"]["code"] == "invalid_webhook"
