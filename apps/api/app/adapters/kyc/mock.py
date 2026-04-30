"""Mock KYC adapter — deterministic outcomes via email-pattern hints.

Email rules (case-insensitive, tag-style):

- ``you+kyc_fail@example.com``     -> FAILED with a reason.
- ``you+kyc_pending@example.com``  -> PENDING (stays pending until
  ``resolve_pending(...)`` is called — exposed for tests / demo).
- anything else                    -> SUCCESS.
"""

from __future__ import annotations

import secrets
from typing import Any
from uuid import UUID

from app.adapters.kyc.base import KycCheckResult
from app.models.kyc import KycStatus


def _ref() -> str:
    return f"mock-kyc-{secrets.token_hex(8)}"


class MockKycAdapter:
    """In-process mock vendor.

    The pending registry is per-instance (DI handles this) but module-level
    helpers in tests can hold a reference and resolve checks deterministically.
    """

    name = "mock"

    def __init__(self) -> None:
        # provider_reference -> latest result (used by fetch_status + the
        # test seam ``resolve_pending``).
        self._pending: dict[str, KycCheckResult] = {}

    async def submit_check(
        self,
        *,
        user_id: UUID,
        email: str,
        full_name: str | None,
        nationality: str | None,
        domicile: str | None,
    ) -> KycCheckResult:
        local = email.split("@", 1)[0].lower()

        raw_meta: dict[str, Any] = {
            "provider": self.name,
            "user_id": str(user_id),
            "captured": {
                "full_name_present": full_name is not None,
                "nationality": nationality,
                "domicile": domicile,
            },
        }

        if "+kyc_fail" in local:
            return KycCheckResult(
                status=KycStatus.FAILED,
                provider_reference=_ref(),
                failure_reason="document_quality_insufficient",
                raw=raw_meta | {"decision": "deny"},
            )

        if "+kyc_pending" in local:
            ref = _ref()
            result = KycCheckResult(
                status=KycStatus.PENDING,
                provider_reference=ref,
                raw=raw_meta | {"decision": "review_in_progress"},
            )
            self._pending[ref] = result
            return result

        return KycCheckResult(
            status=KycStatus.SUCCESS,
            provider_reference=_ref(),
            raw=raw_meta | {"decision": "approve"},
        )

    async def fetch_status(self, *, provider_reference: str) -> KycCheckResult:
        return self._pending.get(
            provider_reference,
            KycCheckResult(
                status=KycStatus.SUCCESS,
                provider_reference=provider_reference,
                raw={"provider": self.name, "decision": "approve"},
            ),
        )

    # ---- test / demo seam ----------------------------------------------

    def resolve_pending(
        self,
        provider_reference: str,
        *,
        status: KycStatus,
        failure_reason: str | None = None,
    ) -> None:
        """Flip a pending check to a terminal state (used by tests + the
        eventual scheduled resolver in slice 7)."""
        if status not in {KycStatus.SUCCESS, KycStatus.FAILED}:
            raise ValueError("can only resolve to SUCCESS or FAILED")
        existing = self._pending.get(provider_reference)
        raw = (existing.raw if existing else {}) | {"decision": status.value}
        self._pending[provider_reference] = KycCheckResult(
            status=status,
            provider_reference=provider_reference,
            failure_reason=failure_reason,
            raw=raw,
        )
