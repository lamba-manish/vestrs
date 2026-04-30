"""Redis-backed sliding-window rate limiting.

Each ``RateLimit(times, seconds)`` is a FastAPI dependency. On each request:
1. Build a key from a per-route bucket + caller identifier (user_id or IP).
2. Use Redis ZSET: drop entries older than the window; count current entries;
   if over budget, raise ``RateLimitedError``; else add a new entry and
   PEXPIRE the key.

Requires Redis. If Redis is unreachable we open the gate and log loudly —
production must monitor for that condition.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import time

import redis.asyncio as aioredis
from fastapi import FastAPI, Request

from app.core.config import Settings
from app.core.errors import RateLimitedError
from app.core.logging import get_logger

log = get_logger("api.rate_limit")

_redis: aioredis.Redis[str] | None = None


@asynccontextmanager
async def rate_limiter_lifespan(app: FastAPI, settings: Settings) -> AsyncIterator[None]:
    global _redis
    try:
        _redis = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        # PING surfaces unreachable Redis at startup so we know early.
        await _redis.ping()
        log.info("rate_limiter_ready")
    except Exception as exc:
        log.warning("rate_limiter_unavailable", error=type(exc).__name__)
        _redis = None
    try:
        yield
    finally:
        if _redis is not None:
            # redis-py 5+ exposes aclose(); the typeshed stubs lag behind.
            await _redis.aclose()  # type: ignore[attr-defined]
            _redis = None


async def _identify(request: Request) -> str:
    user_id: str | None = getattr(request.state, "user_id", None)
    if user_id:
        return f"u:{user_id}"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    return f"ip:{ip or 'unknown'}"


class RateLimit:
    """Per-route + per-caller sliding-window limit. Use as a FastAPI dependency."""

    def __init__(self, times: int, seconds: int, *, bucket: str | None = None) -> None:
        if times <= 0 or seconds <= 0:
            raise ValueError("times and seconds must be positive")
        self.times = times
        self.seconds = seconds
        self.bucket = bucket

    async def __call__(self, request: Request) -> None:
        if _redis is None:
            return  # fail open — already logged at startup

        bucket = self.bucket or request.url.path
        caller = await _identify(request)
        key = f"rl:{bucket}:{caller}"
        now_ms = int(time() * 1000)
        window_start = now_ms - self.seconds * 1000

        pipe = _redis.pipeline(transaction=True)
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {f"{now_ms}-{caller}": now_ms})
        pipe.pexpire(key, self.seconds * 1000)
        _, count, _, _ = await pipe.execute()

        if count >= self.times:
            log.info("rate_limited", bucket=bucket, caller=caller, count=int(count))
            raise RateLimitedError()


def limit(times: int, seconds: int, *, bucket: str | None = None) -> RateLimit:
    return RateLimit(times, seconds, bucket=bucket)


# Test helpers — allow tests to bypass / inject Redis.


def _override_redis_for_tests(
    client: aioredis.Redis[str] | None,
) -> Callable[[], Awaitable[None]]:
    global _redis
    previous = _redis
    _redis = client

    async def _restore() -> None:
        global _redis
        _redis = previous

    return _restore
