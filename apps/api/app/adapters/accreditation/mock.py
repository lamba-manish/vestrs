"""Mock accreditation adapter — Redis-backed time-based resolution.

Email rules (case-insensitive):

- ``you+acc_fail@example.com``  → eventual FAILED with a reason.
- anything else                  → eventual SUCCESS.

State is held in Redis (``acc:pending:<provider_reference>``) so the API and
the ARQ worker (different processes) share the same registry. ``submit_check``
returns ``PENDING`` immediately and stamps a future ``resolves_at``;
``fetch_status`` returns ``PENDING`` until ``now() >= resolves_at``, then the
terminal status.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis

from app.adapters.accreditation.base import AccreditationCheckResult
from app.core.config import get_settings
from app.models.accreditation import AccreditationStatus

REGISTRY_KEY_PREFIX = "acc:pending:"
REGISTRY_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days — outlasts any real review


def _now() -> datetime:
    return datetime.now(UTC)


def _ref() -> str:
    return f"mock-acc-{secrets.token_hex(8)}"


def _key(reference: str) -> str:
    return f"{REGISTRY_KEY_PREFIX}{reference}"


class MockAccreditationAdapter:
    """Redis-backed mock so the API and the ARQ worker share the registry."""

    name = "mock"

    def __init__(self) -> None:
        self._redis: aioredis.Redis[str] | None = None

    def _client(self) -> aioredis.Redis[str]:
        if self._redis is None:
            self._redis = aioredis.from_url(
                get_settings().redis_url, encoding="utf-8", decode_responses=True
            )
        return self._redis

    async def submit_check(
        self,
        *,
        user_id: UUID,
        email: str,
        full_name: str | None,
        nationality: str | None,
        domicile: str | None,
        delay_seconds: int,
    ) -> AccreditationCheckResult:
        local = email.split("@", 1)[0].lower()
        will_fail = "+acc_fail" in local
        ref = _ref()
        resolves_at = _now() + timedelta(seconds=delay_seconds)
        raw = {
            "provider": self.name,
            "user_id": str(user_id),
            "captured": {
                "full_name_present": full_name is not None,
                "nationality": nationality,
                "domicile": domicile,
            },
        }
        entry = {
            "resolves_at": resolves_at.isoformat(),
            "terminal": (
                AccreditationStatus.FAILED.value if will_fail else AccreditationStatus.SUCCESS.value
            ),
            "failure_reason": ("income_documentation_insufficient" if will_fail else None),
            "raw": raw,
            "forced_terminal": False,
        }
        await self._client().setex(_key(ref), REGISTRY_TTL_SECONDS, json.dumps(entry))
        return AccreditationCheckResult(
            status=AccreditationStatus.PENDING,
            provider_reference=ref,
            raw=raw | {"decision": "review_in_progress"},
        )

    async def fetch_status(self, *, provider_reference: str) -> AccreditationCheckResult:
        raw_entry = await self._client().get(_key(provider_reference))
        if raw_entry is None:
            return AccreditationCheckResult(
                status=AccreditationStatus.SUCCESS,
                provider_reference=provider_reference,
                raw={
                    "provider": self.name,
                    "decision": "approve",
                    "warning": "no_registry_entry",
                },
            )

        entry: dict[str, Any] = json.loads(raw_entry)
        resolves_at = datetime.fromisoformat(entry["resolves_at"])
        terminal_status = AccreditationStatus(entry["terminal"])

        if not entry.get("forced_terminal", False) and _now() < resolves_at:
            return AccreditationCheckResult(
                status=AccreditationStatus.PENDING,
                provider_reference=provider_reference,
                raw=entry["raw"] | {"decision": "review_in_progress"},
            )
        return AccreditationCheckResult(
            status=terminal_status,
            provider_reference=provider_reference,
            failure_reason=entry.get("failure_reason"),
            raw=entry["raw"] | {"decision": terminal_status.value},
        )

    async def force_resolve(
        self,
        provider_reference: str,
        *,
        status: AccreditationStatus,
        failure_reason: str | None = None,
    ) -> None:
        if status not in {AccreditationStatus.SUCCESS, AccreditationStatus.FAILED}:
            raise ValueError("can only force-resolve to SUCCESS or FAILED")
        existing_raw = await self._client().get(_key(provider_reference))
        existing: dict[str, Any] = json.loads(existing_raw) if existing_raw else {"raw": {}}
        entry = {
            "resolves_at": _now().isoformat(),
            "terminal": status.value,
            "failure_reason": failure_reason,
            "raw": existing.get("raw", {}),
            "forced_terminal": True,
        }
        await self._client().setex(
            _key(provider_reference), REGISTRY_TTL_SECONDS, json.dumps(entry)
        )

    async def aclose(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()  # type: ignore[attr-defined]
            self._redis = None
