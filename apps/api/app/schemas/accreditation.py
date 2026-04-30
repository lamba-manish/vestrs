"""Accreditation API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AccreditationCheckPublic(BaseModel):
    id: UUID
    attempt_number: int
    status: str
    provider_name: str
    provider_reference: str | None = None
    failure_reason: str | None = None
    requested_at: datetime
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AccreditationSummary(BaseModel):
    """GET /accreditation aggregate state."""

    status: str
    latest: AccreditationCheckPublic | None = None
