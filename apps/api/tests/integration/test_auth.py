from __future__ import annotations

import httpx

from tests.integration.conftest import People, sign_in


async def test_wrong_passwords_and_unknown_accounts_look_the_same(
    people: People, http: httpx.AsyncClient
) -> None:
    wrong = await http.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "nope-nope-1"}
    )
    unknown = await http.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-1"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]
    assert (await http.get("/api/v1/projects")).status_code == 401


async def test_password_change_ends_other_sessions_and_logout_revokes(
    people: People, http: httpx.AsyncClient
) -> None:
    created = await people.admin.ok(
        await people.admin.post(
            "/users", {"email": "temp@example.com", "name": "Temp", "role": "member"}
        )
    )
    first = await sign_in(http, "temp@example.com", created["temporary_password"])
    other = await sign_in(http, "temp@example.com", created["temporary_password"])
    changed = await first.post(
        "/auth/password",
        {
            "current_password": created["temporary_password"],
            "new_password": "A-Better-Passphrase-77",
        },
    )
    assert changed.status_code == 200
    assert (await other.get("/auth/me")).status_code == 401
    refreshed = httpx.AsyncClient(
        transport=http._transport,
        base_url="http://api.test",
        headers={"authorization": f"Bearer {changed.json()['token']}"},
    )
    assert (await refreshed.get("/api/v1/auth/me")).status_code == 200
    assert (await refreshed.post("/api/v1/auth/logout")).status_code == 204
    assert (await refreshed.get("/api/v1/auth/me")).status_code == 401
    weak = await first.post(
        "/auth/password", {"current_password": "x", "new_password": "A-Better-Passphrase-77"}
    )
    assert weak.status_code == 401
    for client in (first.http, other.http, refreshed):
        await client.aclose()


async def test_role_changes_apply_immediately_and_the_last_admin_stays(
    people: People, http: httpx.AsyncClient
) -> None:
    created = await people.admin.ok(
        await people.admin.post(
            "/users", {"email": "shift@example.com", "name": "Shift", "role": "member"}
        )
    )
    session = await sign_in(http, "shift@example.com", created["temporary_password"])
    assert (await session.get("/auth/me")).status_code == 200
    await people.admin.ok(
        await people.admin.patch(f"/users/{created['user']['id']}", {"role": "viewer"})
    )
    # The session ended with the role change.
    assert (await session.get("/auth/me")).status_code == 401
    users = (await people.admin.ok(await people.admin.get("/users")))["items"]
    admin = next(u for u in users if u["email"] == "admin@example.com")
    refused = await people.admin.patch(f"/users/{admin['id']}", {"role": "member"})
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "last_admin"
    assert (await people.viewer.get("/users")).status_code == 403
    await session.http.aclose()
