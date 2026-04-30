"""KYC provider protocol — what every implementation must satisfy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from app.models.kyc import KycStatus


@dataclass(frozen=True)
class KycCheckResult:
    status: KycStatus
    provider_reference: str
    failure_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class KycProvider(Protocol):
    """Vendor-facing port. All adapters in app/adapters/kyc/* satisfy this."""

    name: str

    async def submit_check(
        self,
        *,
        user_id: UUID,
        email: str,
        full_name: str | None,
        nationality: str | None,
        domicile: str | None,
    ) -> KycCheckResult:
        """Run a fresh check. May return a terminal status (success/failed)
        or pending — pending means the vendor will resolve later and the
        caller should poll ``fetch_status``."""
        ...

    async def fetch_status(self, *, provider_reference: str) -> KycCheckResult:
        """Re-query the vendor for an in-flight (pending) check."""
        ...
