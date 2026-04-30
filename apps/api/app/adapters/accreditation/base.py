"""Accreditation provider Protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from app.models.accreditation import AccreditationStatus


@dataclass(frozen=True)
class AccreditationCheckResult:
    status: AccreditationStatus
    provider_reference: str
    failure_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class AccreditationProvider(Protocol):
    name: str

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
        """Start a new accreditation review. Almost always returns
        ``PENDING`` — vendors don't decide on the spot."""
        ...

    async def fetch_status(self, *, provider_reference: str) -> AccreditationCheckResult:
        """Re-query the vendor for an in-flight check."""
        ...
