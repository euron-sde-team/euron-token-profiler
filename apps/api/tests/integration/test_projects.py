from __future__ import annotations

import httpx

from tests.integration.conftest import People
from tests.integration.support import Project


async def test_first_run_state_and_roles(people: People, http: httpx.AsyncClient) -> None:
    info = (await http.get("/api/v1/system/info")).json()
    assert info["needs_setup"] is False
    me = await people.viewer.ok(await people.viewer.get("/auth/me"))
    assert me["role"] == "viewer"
    # A second setup is refused once an administrator exists.
    again = await http.post(
        "/api/v1/auth/setup",
        json={"email": "x@example.com", "name": "X", "password": "Another-Pass-1234"},
    )
    assert again.status_code == 403


async def test_only_admins_create_projects_and_members_manage_keys(
    people: People, project: Project
) -> None:
    assert (await people.member.post("/projects", {"name": "Nope"})).status_code == 403
    assert (await people.viewer.post(f"{project.base}/keys", {"name": "k"})).status_code == 403
    made = await people.member.post(f"{project.base}/keys", {"name": "member key"})
    created = await people.member.ok(made)
    assert created["key"].startswith("tp_")
    assert created["created_by_name"] == "Member"
    listing = await people.viewer.ok(await people.viewer.get(f"{project.base}/keys"))
    assert listing["total"] >= 2
    assert all("key" not in item for item in listing["items"])


async def test_revoked_keys_stop_working(people: People, project: Project) -> None:
    keys = (await project.get("/keys"))["items"]
    await people.admin.ok(await people.admin.delete(f"{project.base}/keys/{keys[0]['id']}"))
    response = await project.http.post(
        "/v1/ingest", json={}, headers={"authorization": f"Bearer {project.key}"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


async def test_settings_are_validated_and_audited(people: People, project: Project) -> None:
    updated = await people.admin.ok(
        await people.admin.patch(
            project.base,
            {
                "sampling_rate": 0.5,
                "retention_days": 7,
                "keep_slow_ms": 4000,
                "redaction": {
                    "detectors": ["email"],
                    "custom": [{"name": "emp", "pattern": r"EMP-\d{6}"}],
                    "max_payload_chars": 500,
                },
            },
        )
    )
    assert float(updated["sampling_rate"]) == 0.5
    assert updated["redaction"]["custom"][0]["replacement"] == "[REDACTED]"
    bad = await people.admin.patch(
        project.base, {"redaction": {"custom": [{"name": "x", "pattern": "(a+)+"}]}}
    )
    assert bad.status_code == 422
    assert (await people.member.patch(project.base, {"retention_days": 3})).status_code == 403
    audit = await people.admin.ok(await people.admin.get("/audit", project_id=project.id))
    assert "project.updated" in {event["action"] for event in audit["items"]}
    assert (await people.member.get("/audit")).status_code == 403


async def test_redaction_preview(people: People, project: Project) -> None:
    result = await people.member.ok(
        await people.member.post(
            f"{project.base}/redaction/test", {"text": "write to jo@example.com today"}
        )
    )
    assert result["redacted"] == "write to [REDACTED:email] today"
    assert result["by_rule"] == {"email": 1}
    assert (
        await people.viewer.post(f"{project.base}/redaction/test", {"text": "a@example.com"})
    ).status_code == 403


async def test_webhook_urls_are_sealed_and_never_returned(people: People, project: Project) -> None:
    updated = await people.admin.ok(
        await people.admin.patch(project.base, {"webhook_url": "http://hooks.example.com/t/secret"})
    )
    assert updated["has_webhook"] is True
    assert "secret" not in str(updated)
    bad = await people.admin.patch(project.base, {"webhook_url": "ftp://x"})
    assert bad.status_code == 422
    cleared = await people.admin.ok(await people.admin.patch(project.base, {"webhook_url": ""}))
    assert cleared["has_webhook"] is False


async def test_deleting_a_project_removes_its_data(people: People, project: Project) -> None:
    await project.send(
        [{"id": "s1", "trace_id": "t1", "name": "x", "start_time": "2026-11-18T10:00:00Z"}]
    )
    assert (await people.admin.delete(project.base)).status_code == 204
    assert (await people.admin.get(project.base)).status_code == 404
