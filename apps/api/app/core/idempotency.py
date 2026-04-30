"""Redis-backed idempotency store.

Used by ``POST /api/v1/investments`` (CLAUDE.md sec. 5: required on every
state-changing endpoint that handles money).

Keying:
- The full Redis key is ``idem:user:<user_id>:<idempotency_key>``.
- Stored value is JSON ``{"body_hash", "status_code", "response"}``.
- TTL: 24 hours (matches Stripe's idempotency window — long enough for
  typical retry storms, short enough to bound storage).

On replay:
- Same key + same body hash → return the stored response verbatim.
- Same key + different body hash → ``IDEMPOTENCY_KEY_REUSED`` (the caller
  reused the key on a different request, almost certainly a bug).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis

from app.core.config import get_settings

KEY_PREFIX = "idem:user:"
TTL_SECONDS = 60 * 60 * 24


def hash_body(body: dict[str, Any]) -> str:
    """Stable hash over the request body. ``sort_keys`` keeps order-insensitive."""
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StoredResult:
    body_hash: str
    status_code: int
    response: dict[str, Any]


class IdempotencyStore:
    def __init__(self) -> None:
        self._redis: aioredis.Redis[str] | None = None

    def _client(self) -> aioredis.Redis[str]:
        if self._redis is None:
            self._redis = aioredis.from_url(
                get_settings().redis_url, encoding="utf-8", decode_responses=True
            )
        return self._redis

    @staticmethod
    def _key(user_id: UUID, idempotency_key: str) -> str:
        return f"{KEY_PREFIX}{user_id}:{idempotency_key}"

    async def get(self, user_id: UUID, idempotency_key: str) -> StoredResult | None:
        raw = await self._client().get(self._key(user_id, idempotency_key))
        if raw is None:
            return None
        data: dict[str, Any] = json.loads(raw)
        return StoredResult(
            body_hash=data["body_hash"],
            status_code=int(data["status_code"]),
            response=data["response"],
        )

    async def store(
        self,
        user_id: UUID,
        idempotency_key: str,
        *,
        body_hash: str,
        status_code: int,
        response: dict[str, Any],
    ) -> None:
        payload = json.dumps(
            {
                "body_hash": body_hash,
                "status_code": status_code,
                "response": response,
            }
        )
        await self._client().setex(self._key(user_id, idempotency_key), TTL_SECONDS, payload)

    async def aclose(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()  # type: ignore[attr-defined]
            self._redis = None
