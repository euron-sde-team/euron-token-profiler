"""Process-wide infrastructure, built once at startup and shared by every request.

Services are cheap objects created per request around one database session; everything
expensive or stateful (pools, the price cache, the archive client, the webhook client) lives
here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from redis.asyncio import Redis

from tokenprofiler.core.config import Settings
from tokenprofiler.core.ratelimit import RateLimiter
from tokenprofiler.core.secretbox import SecretBox
from tokenprofiler.db.session import Database
from tokenprofiler.integrations.archive import ArchiveStore, build_archive
from tokenprofiler.services.pricebook import PriceBooks


@dataclass
class Container:
    settings: Settings
    db: Database
    redis: Redis
    limiter: RateLimiter
    secretbox: SecretBox
    archive: ArchiveStore
    prices: PriceBooks
    http: httpx.AsyncClient = field(
        default_factory=lambda: httpx.AsyncClient(follow_redirects=False)
    )

    async def close(self) -> None:
        await self.http.aclose()
        await self.redis.aclose()
        await self.db.dispose()


async def build_container(settings: Settings) -> Container:
    redis = Redis.from_url(
        settings.redis_url, decode_responses=False, health_check_interval=30, socket_timeout=5
    )
    db = Database(settings)
    return Container(
        settings=settings,
        db=db,
        redis=redis,
        limiter=RateLimiter(redis),
        secretbox=SecretBox(settings.encryption_key.get_secret_value()),
        archive=build_archive(settings),
        prices=PriceBooks(db, settings.price_cache_ttl_s),
        http=httpx.AsyncClient(timeout=settings.webhook_timeout_s, follow_redirects=False),
    )
