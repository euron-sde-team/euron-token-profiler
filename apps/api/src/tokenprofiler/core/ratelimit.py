"""Fixed-window limits in Valkey: requests per minute and tokens per minute.

One pipeline per request counts the request and reads the tokens already spent in the
window; the tokens a request actually used are added when it finishes. A single request
can therefore overshoot the token limit once, an accepted trade for not having to predict
how long an answer will be. Fixed windows also allow a short burst at a window boundary,
in exchange for O(1) memory per caller.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_s: int

    def headers(self) -> dict[str, str]:
        return {
            "x-ratelimit-limit": str(self.limit),
            "x-ratelimit-remaining": str(self.remaining),
            "x-ratelimit-reset": str(self.reset_s),
        }


@dataclass(frozen=True, slots=True)
class UsageWindow:
    """Both limits for one caller, in OpenAI's header vocabulary."""

    requests_allowed: bool
    tokens_allowed: bool
    request_limit: int
    requests_remaining: int
    token_limit: int
    tokens_remaining: int
    reset_s: int

    @property
    def allowed(self) -> bool:
        return self.requests_allowed and self.tokens_allowed

    def headers(self) -> dict[str, str]:
        reset = f"{self.reset_s}s"
        return {
            "x-ratelimit-limit-requests": str(self.request_limit),
            "x-ratelimit-remaining-requests": str(self.requests_remaining),
            "x-ratelimit-reset-requests": reset,
            "x-ratelimit-limit-tokens": str(self.token_limit),
            "x-ratelimit-remaining-tokens": str(self.tokens_remaining),
            "x-ratelimit-reset-tokens": reset,
        }


class RateLimiter:
    def __init__(self, redis: Redis, window_s: int = 60) -> None:
        self._redis = redis
        self.window_s = window_s

    def _bucket(self, now: float) -> tuple[int, int]:
        bucket = int(now // self.window_s)
        reset_s = int(self.window_s - (now % self.window_s)) or self.window_s
        return bucket, reset_s

    async def hit(self, key: str, limit: int) -> RateLimitResult:
        """Count one attempt against a plain per-minute limit (sign-in attempts)."""
        bucket, reset_s = self._bucket(time.time())
        redis_key = f"rl:{key}:{bucket}"
        async with self._redis.pipeline(transaction=False) as pipe:
            pipe.incr(redis_key)
            pipe.expire(redis_key, self.window_s + 1, nx=True)
            count, _ = await pipe.execute()
        return RateLimitResult(
            allowed=int(count) <= limit,
            limit=limit,
            remaining=max(0, limit - int(count)),
            reset_s=reset_s,
        )

    async def admit(self, key: str, rpm: int, tpm: int) -> UsageWindow:
        """Count a request and check the token budget already spent in this window."""
        bucket, reset_s = self._bucket(time.time())
        requests_key = f"rl:req:{key}:{bucket}"
        tokens_key = f"rl:tok:{key}:{bucket}"
        async with self._redis.pipeline(transaction=False) as pipe:
            pipe.incr(requests_key)
            pipe.expire(requests_key, self.window_s + 1, nx=True)
            pipe.get(tokens_key)
            count, _, spent_raw = await pipe.execute()
        spent = int(spent_raw or 0)
        return UsageWindow(
            requests_allowed=int(count) <= rpm,
            tokens_allowed=spent < tpm,
            request_limit=rpm,
            requests_remaining=max(0, rpm - int(count)),
            token_limit=tpm,
            tokens_remaining=max(0, tpm - spent),
            reset_s=reset_s,
        )

    async def spend(self, key: str, tokens: int) -> None:
        """Add the tokens a finished request used to the current window."""
        if tokens <= 0:
            return
        bucket, _ = self._bucket(time.time())
        tokens_key = f"rl:tok:{key}:{bucket}"
        async with self._redis.pipeline(transaction=False) as pipe:
            pipe.incrby(tokens_key, tokens)
            pipe.expire(tokens_key, self.window_s + 1, nx=True)
            await pipe.execute()
