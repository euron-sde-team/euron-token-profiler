"""Helpers for the integration suite: a signed-in client, a project and a long-lived context."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

import httpx

PASSWORD = "Integration-Pass-9137!"


class Api:
    """The control plane as one signed-in person (bearer token), over ASGI."""

    def __init__(self, http: httpx.AsyncClient, email: str) -> None:
        self.http = http
        self.email = email

    async def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        return await self.http.request(method, f"/api/v1{path}", **kwargs)

    async def get(self, path: str, **params: Any) -> httpx.Response:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
        return await self.request("POST", path, json=body or {})

    async def patch(self, path: str, body: dict[str, Any]) -> httpx.Response:
        return await self.request("PATCH", path, json=body)

    async def delete(self, path: str) -> httpx.Response:
        return await self.request("DELETE", path)

    async def ok(self, response: httpx.Response) -> Any:
        assert response.status_code < 300, f"{response.status_code}: {response.text}"
        return response.json() if response.content else None


@contextlib.asynccontextmanager
async def held[T](manager: contextlib.AbstractAsyncContextManager[T]) -> AsyncIterator[T]:
    """Enter an async context in a task of its own and keep it open until the block ends.

    The application lifespan starts and stops background tasks and must be exited by the
    task that entered it, but a pytest fixture's setup and teardown run in different tasks.
    """
    ready: asyncio.Future[T] = asyncio.get_running_loop().create_future()
    release = asyncio.Event()

    async def run() -> None:
        try:
            async with manager as value:
                ready.set_result(value)
                await release.wait()
        except BaseException as exc:
            if not ready.done():
                ready.set_exception(exc)
            else:
                raise

    task = asyncio.create_task(run())
    try:
        yield await ready
    finally:
        release.set()
        await task


class Project:
    """A fresh project with an ingest key, so each test works on data of its own."""

    def __init__(self, api: Api, http: httpx.AsyncClient, data: dict[str, Any], key: str) -> None:
        self.api = api
        self.http = http
        self.id: str = data["id"]
        self.slug: str = data["slug"]
        self.key = key

    @property
    def base(self) -> str:
        return f"/projects/{self.id}"

    async def send(
        self, spans: list[dict[str, Any]], traces: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        response = await self.http.post(
            "/v1/ingest",
            json={"spans": spans, "traces": traces or []},
            headers={"authorization": f"Bearer {self.key}"},
        )
        assert response.status_code == 200, response.text
        result: dict[str, Any] = response.json()
        return result

    async def get(self, path: str, **params: Any) -> Any:
        return await self.api.ok(await self.api.get(f"{self.base}{path}", **params))
