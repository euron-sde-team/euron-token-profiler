"""The FastAPI application factory.

uvicorn tokenprofiler.main:create_app --factory --port 8210
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tokenprofiler import __version__
from tokenprofiler.api.router import api_router
from tokenprofiler.core.config import Settings, get_settings
from tokenprofiler.core.context import BodySizeLimitMiddleware, RequestContextMiddleware
from tokenprofiler.core.errors import install_exception_handlers
from tokenprofiler.core.logging import configure_logging, get_logger
from tokenprofiler.db.migrate import migrate
from tokenprofiler.services.container import build_container
from tokenprofiler.services.prices import sync_builtin_prices

log = get_logger("tokenprofiler.app")

DESCRIPTION = """
LLM observability: traces, token and cost attribution, prompts, budgets and alerts.

**Ingest plane** (`/v1`): send `Authorization: Bearer tp_...` with a project API key.
`POST /v1/ingest` takes the native batch the Python SDK sends; `POST /v1/otlp/v1/traces`
takes OpenTelemetry OTLP/HTTP (JSON or protobuf, gzip accepted). `GET /v1/prompts/{name}`
fetches a managed prompt.

**Control plane** (`/api/v1`): projects, traces, metrics, prompts, prices, budgets, alerts
and people, for signed-in users (session cookie or `Bearer <session token>`).

Every error uses one envelope: `{"error": {"code", "message", "request_id", "details?"}}`.
"""

TAGS = [
    {"name": "ingest", "description": "Native and OpenTelemetry trace ingest, prompt fetch."},
    {"name": "projects", "description": "Projects, sampling, redaction, retention and keys."},
    {"name": "traces", "description": "Trace list, search, filters and the span tree."},
    {"name": "metrics", "description": "Overview and breakdowns by model, agent, tool, prompt."},
    {"name": "prompts", "description": "Prompt versions, labels and usage."},
    {"name": "prices", "description": "The model price table and per-project overrides."},
    {"name": "budgets and alerts", "description": "Spend budgets, alert rules and their events."},
    {"name": "archives", "description": "Traces archived by retention."},
    {"name": "auth", "description": "Sign-in, first-run setup, sessions and your profile."},
    {"name": "users", "description": "People and roles."},
    {"name": "system", "description": "Deployment info and the audit trail."},
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)
    if settings.is_production and (problems := settings.production_problems()):
        raise RuntimeError("Refusing to start in production:\n  - " + "\n  - ".join(problems))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.migrate_on_boot:
            await migrate(settings)
        container = await build_container(settings)
        app.state.container = container
        prices = await sync_builtin_prices(container)
        log.info(
            "started",
            version=__version__,
            env=settings.app_env,
            node=settings.node_name,
            builtin_prices=prices,
            archive=settings.archive_store,
        )
        try:
            yield
        finally:
            await container.close()
            log.info("stopped")

    app = FastAPI(
        title=settings.product_name,
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
        license_info={"name": "MIT", "identifier": "MIT"},
    )
    install_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["authorization", "content-type", "x-request-id", "x-api-key"],
        expose_headers=[
            "x-request-id",
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "x-ratelimit-reset",
            "retry-after",
        ],
        max_age=600,
    )
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(RequestContextMiddleware, hsts=settings.is_production)
    app.include_router(api_router)
    return app
