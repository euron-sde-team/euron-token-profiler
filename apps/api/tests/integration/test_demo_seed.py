from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from tests.integration.conftest import make_settings, recreate_database
from tokenprofiler.db.migrate import migrate
from tokenprofiler.demo import seed as demo
from tokenprofiler.services.container import build_container


async def test_demo_seed_builds_a_lived_in_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = "tokenprofiler_seed_test"
    await recreate_database(name)
    from tests.integration import conftest

    settings = make_settings(
        tmp_path, database_url=conftest.database_url(name), demo_password="Demo-Password-1234"
    )
    await migrate(settings)
    monkeypatch.setattr(demo, "VOLUME_SCALE", 0.15)
    report = await demo.seed(settings)
    assert "seeded" in report
    assert "tp_" in report
    assert "already present" in await demo.seed(settings)

    container = await build_container(settings)
    try:
        async with container.db.session() as session:

            async def one(sql: str) -> int:
                return int((await session.execute(text(sql))).scalar_one())

            assert await one("SELECT count(*) FROM projects") == 2
            assert await one("SELECT count(*) FROM users") == 3
            assert await one("SELECT count(*) FROM traces") > 100
            assert await one("SELECT count(DISTINCT agent_name) FROM spans") >= 4
            assert await one("SELECT count(DISTINCT tool_name) FROM spans") >= 5
            assert await one("SELECT count(DISTINCT model) FROM spans") >= 8
            assert await one("SELECT count(*) FROM traces WHERE status = 'error'") > 0
            assert await one("SELECT count(*) FROM prompt_versions WHERE managed") >= 18
            assert await one("SELECT count(*) FROM budgets") == 4
            assert await one("SELECT count(*) FROM alert_events") >= 1
            # Redaction ran on the seeded traffic: no raw email survives in payloads.
            assert (
                await one(
                    "SELECT count(*) FROM spans WHERE input ~ '[a-z]+\\.[0-9]+@example\\.com'"
                )
                == 0
            )
            # Every trace total equals the sum of its metered spans.
            assert (
                await one(
                    """SELECT count(*) FROM traces t WHERE abs(t.total_cost - coalesce((
                        SELECT sum(total_cost) FROM spans s
                        WHERE s.project_id = t.project_id AND s.trace_id = t.id
                          AND s.kind IN ('generation', 'embedding')), 0)) > 0.00000001"""
                )
                == 0
            )
    finally:
        await container.close()
