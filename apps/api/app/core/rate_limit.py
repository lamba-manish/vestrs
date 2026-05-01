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


def get_redis() -> aioredis.Redis[str] | None:
    """Module-level accessor for the lifespan-bound Redis client.
    Used by /healthz so we don't open a second connection just to ping."""
    return _redis


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


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


async def _identify(request: Request, *, force_ip: bool = False) -> str:
    if not force_ip:
        user_id: str | None = getattr(request.state, "user_id", None)
        if user_id:
            return f"u:{user_id}"
    return f"ip:{_client_ip(request)}"


class RateLimit:
    """Per-route + per-caller sliding-window limit. FastAPI dependency.

    `identify_by="ip"` forces IP-based bucketing even when the request
    is authenticated — used by the global per-IP limit so a single
    user can't dodge the IP cap by signing in.
    """

    def __init__(
        self,
        times: int,
        seconds: int,
        *,
        bucket: str | None = None,
        identify_by: str = "auto",
    ) -> None:
        if times <= 0 or seconds <= 0:
            raise ValueError("times and seconds must be positive")
        if identify_by not in {"auto", "ip"}:
            raise ValueError("identify_by must be 'auto' or 'ip'")
        self.times = times
        self.seconds = seconds
        self.bucket = bucket
        self.identify_by = identify_by

    async def __call__(self, request: Request) -> None:
        if _redis is None:
            return  # fail open — already logged at startup

        bucket = self.bucket or request.url.path
        caller = await _identify(request, force_ip=self.identify_by == "ip")
        key = f"rl:{bucket}:{caller}"
        now_ms = int(time() * 1000)
        window_start = now_ms - self.seconds * 1000

        pipe = _redis.pipeline(transaction=True)
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {f"{now_ms}-{caller}": now_ms})
        pipe.pexpire(key, self.seconds * 1000)
        # Peek the oldest in-window entry so we can compute Retry-After
        # accurately when over budget.
        pipe.zrange(key, 0, 0, withscores=True)
        _, count, _, _, oldest = await pipe.execute()

        if count >= self.times:
            retry_after = self._retry_after_from_oldest(oldest, now_ms)
            log.info(
                "rate_limited",
                bucket=bucket,
                caller=caller,
                count=int(count),
                retry_after_seconds=retry_after,
            )
            raise RateLimitedError(retry_after_seconds=retry_after)

    def _retry_after_from_oldest(self, oldest: list[tuple[str, float]], now_ms: int) -> int:
        # The oldest entry falls out of the window in
        # (oldest_score + window) - now milliseconds. Round up to
        # whole seconds; floor at 1s so clients always see a non-zero
        # delay.
        if not oldest:
            return self.seconds
        _, oldest_score_ms = oldest[0]
        ms_until_clear = int(oldest_score_ms) + self.seconds * 1000 - now_ms
        return max(1, (ms_until_clear + 999) // 1000)


def limit(
    times: int,
    seconds: int,
    *,
    bucket: str | None = None,
    identify_by: str = "auto",
) -> RateLimit:
    return RateLimit(times, seconds, bucket=bucket, identify_by=identify_by)


# Module-level dependency: 100 requests per minute per IP across the
# whole API. Mounted on the v1 router so every authed/anon endpoint
# under /api/v1 shares this budget. Per-route buckets stack on top
# of this for endpoints that need tighter abuse defenses (login,
# signup, kyc, etc.).
global_ip_limit = RateLimit(times=100, seconds=60, bucket="global:ip", identify_by="ip")


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
