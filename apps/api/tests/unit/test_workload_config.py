from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr

from tokenprofiler.core.config import Settings
from tokenprofiler.demo.workload import FLOWS, generate
from tokenprofiler.ingest.attribution import Node, resolve_attribution

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


def build(seed: int = 5) -> list:  # type: ignore[type-arg]
    return generate(seed=seed, now=NOW, days=3, per_weekday=60, flows=dict.fromkeys(FLOWS, 1.0))


def test_the_workload_is_deterministic_and_realistic() -> None:
    first, second = build(), build()
    assert [t.trace_id for b in first for t in b.traces] == [
        t.trace_id for b in second for t in b.traces
    ]
    spans = [s for b in first for s in b.spans]
    assert len(spans) > 500
    assert all(s.ended_at >= s.started_at for s in spans)
    assert all(s.started_at <= NOW for s in spans)
    assert {s.kind for s in spans} >= {"agent", "tool", "generation", "embedding"}
    assert any(s.status == "error" for s in spans)
    assert len({s.model for s in spans if s.model}) >= 8
    assert build(seed=6) != first


def test_every_trace_attributes_cleanly() -> None:
    for batch in build():
        by_trace: dict[str, list[Node]] = {}
        for s in batch.spans:
            by_trace.setdefault(s.trace_id, []).append(
                Node(s.span_id, s.parent_id, s.kind, s.name, s.agent_name, s.tool_name)
            )
        for nodes in by_trace.values():
            roots = [n for n in nodes if n.parent_id is None]
            assert len(roots) == 1
            resolved = resolve_attribution(nodes)
            assert len(resolved) == len(nodes)


def test_traces_stay_inside_the_window() -> None:
    starts = [s.started_at for b in build() for s in b.spans]
    assert min(starts) >= NOW - timedelta(days=3, hours=1)


def test_production_refuses_development_defaults() -> None:
    problems = Settings(app_env="production").production_problems()
    assert any("SESSION_SECRET" in p for p in problems)
    assert any("COOKIE_SECURE" in p for p in problems)
    good = Settings(
        app_env="production",
        session_secret=SecretStr("a" * 40),
        api_key_pepper=SecretStr("b" * 40),
        encryption_key=SecretStr("c" * 40),
        cookie_secure=True,
    )
    assert good.production_problems() == []
    unsafe = good.model_copy(
        update={"webhook_allow_private_hosts": True, "aws_endpoint_url": "http://x"}
    )
    assert len(unsafe.production_problems()) == 2


def test_empty_environment_values_mean_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S3_BUCKET", "")
    assert Settings().s3_bucket is None
