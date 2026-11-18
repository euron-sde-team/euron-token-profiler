"""Runtime configuration, validated once at boot.

Every setting comes from the environment. `get_settings()` is cached, so the whole process
shares one frozen `Settings`. In production, `production_problems()` refuses development
defaults and reports every problem at once instead of one per restart.
"""

from __future__ import annotations

import socket
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Shipped so `uvicorn` starts with zero configuration on a laptop. Production refuses it.
DEV_SECRET = "dev-only-insecure-secret-do-not-use-in-production"  # noqa: S105

AppEnv = Literal["development", "test", "production"]


def _split(value: object) -> object:
    if isinstance(value, str):
        return [part.strip() for part in value.replace(",", " ").split() if part.strip()]
    return value


class Settings(BaseSettings):
    # Compose passes optional settings as empty strings; an empty value means "not set".
    model_config = SettingsConfigDict(extra="ignore", frozen=True, env_ignore_empty=True)

    app_env: AppEnv = "development"
    product_name: str = "Euron TokenProfiler"
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    log_format: Literal["json", "console"] = "json"
    # One API process is one node. The name labels logs and metrics.
    node_name: str = Field(default_factory=lambda: socket.gethostname()[:64] or "node")

    # HTTP
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3210", "http://127.0.0.1:3210"]
    )
    web_url: str = "http://localhost:3210"
    api_url: str = "http://localhost:8210"
    max_request_mb: int = Field(default=16, ge=1, le=256)

    # Postgres
    database_url: str = (
        "postgresql+asyncpg://tokenprofiler:tokenprofiler@localhost:5461/tokenprofiler"
    )
    # On AWS the URL carries no password; it is read from this RDS-managed secret for each
    # new connection, so a rotation needs no redeploy.
    database_secret_arn: str | None = None
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=10, ge=0, le=100)
    database_echo: bool = False
    migrate_on_boot: bool = False

    # Valkey (or Redis): rate limits, revoked sessions, locks, the dashboard cache
    redis_url: str = "redis://localhost:6421/0"

    # Sessions, project API keys and stored webhook URLs
    session_secret: SecretStr = SecretStr(DEV_SECRET)
    session_ttl_hours: int = Field(default=168, ge=1, le=2160)
    api_key_pepper: SecretStr = SecretStr(DEV_SECRET)
    encryption_key: SecretStr = SecretStr(DEV_SECRET)
    cookie_secure: bool = False
    cookie_domain: str | None = None
    allow_signup: bool = False
    rate_limit_login: int = Field(default=10, ge=1)

    # Ingest: per-key request limit (per minute), the largest accepted batch and the largest
    # decompressed OTLP body. Payload fields are always truncated to the project's limit.
    ingest_rate_limit: int = Field(default=1200, ge=1)
    max_batch_items: int = Field(default=5000, ge=1, le=100_000)
    max_decompressed_mb: int = Field(default=64, ge=1, le=1024)

    # Dashboards: aggregates are cached in Valkey for this long
    dashboard_cache_ttl_s: int = Field(default=30, ge=0, le=3600)
    price_cache_ttl_s: int = Field(default=30, ge=1)

    # Background loops in the worker
    alert_interval_s: float = Field(default=30, gt=0)
    retention_interval_s: float = Field(default=600, gt=0)
    retention_batch: int = Field(default=500, ge=10, le=10_000)
    default_retention_days: int = Field(default=30, ge=1, le=3650)

    # Alert webhooks: refuse private addresses unless this is on (development and tests).
    webhook_allow_private_hosts: bool = False
    webhook_timeout_s: float = Field(default=5, gt=0)

    # Archive store for traces removed by retention: S3 (SSE-KMS) or a local directory.
    archive_store: Literal["local", "s3"] = "local"
    archive_dir: Path = Path("data/archive")
    s3_bucket: str | None = None
    s3_prefix: str = "archive"
    s3_kms_key_id: str | None = None
    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None

    demo_password: SecretStr | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_lists(cls, value: object) -> object:
        return _split(value)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def max_request_bytes(self) -> int:
        return self.max_request_mb * 1024 * 1024

    def production_problems(self) -> list[str]:
        """Every reason this configuration is unsafe to serve real users."""
        problems: list[str] = []
        secrets = {
            "SESSION_SECRET": self.session_secret.get_secret_value(),
            "API_KEY_PEPPER": self.api_key_pepper.get_secret_value(),
            "ENCRYPTION_KEY": self.encryption_key.get_secret_value(),
        }
        for name, value in secrets.items():
            if value == DEV_SECRET or len(value) < 32:
                problems.append(f"{name} must be a random value of at least 32 characters")
        if len(set(secrets.values())) < len(secrets):
            problems.append("SESSION_SECRET, API_KEY_PEPPER and ENCRYPTION_KEY must all differ")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true behind HTTPS")
        if not self.cors_origins or "*" in self.cors_origins:
            problems.append("CORS_ORIGINS must list the web app origins explicitly")
        if self.aws_endpoint_url:
            problems.append("AWS_ENDPOINT_URL points at an emulator; unset it in production")
        if self.webhook_allow_private_hosts:
            problems.append("WEBHOOK_ALLOW_PRIVATE_HOSTS must be false (SSRF guard)")
        if self.archive_store == "s3" and not self.s3_bucket:
            problems.append("ARCHIVE_STORE=s3 needs S3_BUCKET")
        return problems


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
