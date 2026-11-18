from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest

from tokenprofiler_sdk import TokenProfiler
from tokenprofiler_sdk import client as client_module


class Server:
    """A fake TokenProfiler API that records what the SDK sends."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.statuses: list[int] = []
        self.prompt: dict[str, Any] | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path.startswith("/v1/prompts/"):
            if self.prompt is None:
                return httpx.Response(404, json={"error": {"code": "not_found"}})
            return httpx.Response(200, json=self.prompt)
        status = self.statuses.pop(0) if self.statuses else 200
        return httpx.Response(status, json={"accepted_spans": 0})

    @property
    def spans(self) -> list[dict[str, Any]]:
        return [s for body in self.bodies for s in body["spans"]]

    @property
    def traces(self) -> list[dict[str, Any]]:
        return [t for body in self.bodies for t in body["traces"]]

    @property
    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests if r.url.path == "/v1/ingest"]


@pytest.fixture
def server() -> Server:
    return Server()


@pytest.fixture
def make_client(server: Server) -> Iterator[Callable[..., TokenProfiler]]:
    created: list[TokenProfiler] = []

    def build(**options: Any) -> TokenProfiler:
        options.setdefault("flush_interval", 0.05)
        options.setdefault("max_retries", 2)
        profiler = TokenProfiler(
            "http://api.test", "tp_key", transport=httpx.MockTransport(server.handler), **options
        )
        created.append(profiler)
        return profiler

    yield build
    for profiler in created:
        profiler.shutdown()
    client_module._default = None
