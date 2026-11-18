"""Integration fixtures: real Postgres, Valkey and the Floci AWS emulator.

`make test-integration` starts all three (scripts/test-deps.sh, ports 5461, 6421 and 4621)
and runs this suite. It works in a database of its own (`tokenprofiler_test`, recreated on
every run), Valkey database 15 (flushed on every run) and uniquely named buckets on the
emulator, so nothing else is touched. Point it elsewhere with TEST_DATABASE_ADMIN_URL,
TEST_REDIS_URL and TEST_AWS_ENDPOINT_URL.

The tests run the real application over ASGI, so a request travels the whole path: key,
rate limit, parsing, sampling, pricing, redaction, storage and the dashboards.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import asyncpg
import boto3
import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.engine import URL, make_url

from tests.integration.support import PASSWORD, Api, Project, held
from tokenprofiler.core.config import Settings, get_settings
from tokenprofiler.db.migrate import migrate
from tokenprofiler.main import create_app
from tokenprofiler.services.container import Container

# The emulator accepts any credentials; real ones must never be sent to it.
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
for _name in ("AWS_SESSION_TOKEN", "AWS_PROFILE"):
    os.environ.pop(_name, None)

ADMIN_URL = os.environ.get(
    "TEST_DATABASE_ADMIN_URL",
    "postgresql://tokenprofiler:tokenprofiler@localhost:5461/tokenprofiler",
)
REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6421/15")
AWS_ENDPOINT = os.environ.get("TEST_AWS_ENDPOINT_URL", "http://localhost:4621")
TEST_DATABASE = os.environ.get("TEST_DATABASE_NAME", "tokenprofiler_test")
WEB_ORIGIN = "http://localhost:3210"
RUN = uuid.uuid4().hex[:8]


def database_url(name: str) -> str:
    admin = make_url(ADMIN_URL)
    return URL.create(
        "postgresql+asyncpg",
        username=admin.username,
        password=admin.password,
        host=admin.host,
        port=admin.port,
        database=name,
    ).render_as_string(hide_password=False)


async def recreate_database(name: str) -> None:
    conn = await asyncpg.connect(ADMIN_URL)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


def aws_client(service: str) -> Any:
    return boto3.client(service, endpoint_url=AWS_ENDPOINT, region_name="us-east-1")


def make_settings(archive_dir: Path, **overrides: Any) -> Settings:
    """Test settings, independent of the developer's environment variables."""
    values: dict[str, Any] = {
        "app_env": "test",
        "log_level": "warning",
        "database_url": database_url(TEST_DATABASE),
        "redis_url": REDIS_URL,
        "session_secret": "integration-session-secret-0123456789abcdef",
        "api_key_pepper": "integration-api-key-pepper-0123456789abcdef",
        "encryption_key": "integration-encryption-key-0123456789abcdef",
        "cors_origins": [WEB_ORIGIN],
        "web_url": WEB_ORIGIN,
        "archive_store": "local",
        "archive_dir": archive_dir / "archive",
        "rate_limit_login": 100_000,
        "ingest_rate_limit": 100_000,
        "webhook_allow_private_hosts": True,
        "node_name": "it-node",
    }
    values.update(overrides)
    return Settings.model_validate(values)


@pytest.fixture(scope="session")
async def settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    get_settings.cache_clear()
    settings = make_settings(tmp_path_factory.mktemp("store"))
    await recreate_database(TEST_DATABASE)
    await migrate(settings)
    redis = Redis.from_url(REDIS_URL)
    await redis.flushdb()
    await redis.aclose()
    return settings


@pytest.fixture(scope="session")
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    """The real application, started: database, cache and the builtin price table."""
    application = create_app(settings)
    async with held(application.router.lifespan_context(application)):
        yield application


@pytest.fixture(scope="session")
def container(app: FastAPI) -> Container:
    container: Container = app.state.container
    return container


@pytest.fixture(scope="session")
async def http(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://api.test", timeout=120
    ) as client:
        yield client


async def sign_in(http: httpx.AsyncClient, email: str, password: str) -> Api:
    response = await http.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    # The shared client must not keep the session cookie: the ingest tests rely on it being
    # anonymous unless they send a key.
    http.cookies.clear()
    session = httpx.AsyncClient(
        transport=http._transport,
        base_url="http://api.test",
        timeout=120,
        headers={"authorization": f"Bearer {response.json()['token']}"},
    )
    return Api(session, email)


class People:
    def __init__(self, admin: Api, member: Api, viewer: Api) -> None:
        self.admin = admin
        self.member = member
        self.viewer = viewer


@pytest.fixture(scope="session")
async def people(http: httpx.AsyncClient) -> AsyncIterator[People]:
    """The first-run admin, plus a member and a viewer the admin creates."""
    setup = await http.post(
        "/api/v1/auth/setup",
        json={"email": "admin@example.com", "name": "Ada Admin", "password": PASSWORD},
    )
    assert setup.status_code == 201, setup.text
    http.cookies.clear()
    admin = await sign_in(http, "admin@example.com", PASSWORD)
    apis: dict[str, Api] = {}
    for email, role in (("member@example.com", "member"), ("viewer@example.com", "viewer")):
        created = await admin.post("/users", {"email": email, "name": role.title(), "role": role})
        temporary = (await admin.ok(created))["temporary_password"]
        apis[role] = await sign_in(http, email, temporary)
    yield People(admin, apis["member"], apis["viewer"])
    for api in (admin, *apis.values()):
        await api.http.aclose()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Everything under tests/integration needs the real services: mark it so."""
    for item in items:
        if "tests/integration" in str(item.path).replace("\\", "/"):
            item.add_marker(pytest.mark.integration)


@pytest.fixture
async def project(people: People, http: httpx.AsyncClient) -> Project:
    """A fresh project and ingest key per test, so tests never see each other's traces."""
    created = await people.admin.post("/projects", {"name": f"Test {uuid.uuid4().hex[:6]}"})
    data = await people.admin.ok(created)
    key = await people.admin.ok(
        await people.admin.post(f"/projects/{data['id']}/keys", {"name": "sdk"})
    )
    return Project(people.admin, http, data, key["key"])
