"""KYC API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class KycCheckPublic(BaseModel):
    """One KYC attempt as seen by the client."""

    id: UUID
    attempt_number: int
    status: str
    provider_name: str
    provider_reference: str | None = None
    failure_reason: str | None = None
    requested_at: datetime
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class KycSummary(BaseModel):
    """Aggregate KYC state for the current user — what GET /kyc returns."""

    status: str  # KycStatus value, plus 'not_started' when no rows exist
    attempts_used: int
    attempts_remaining: int
    latest: KycCheckPublic | None = None
