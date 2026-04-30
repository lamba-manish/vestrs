"""Audit-log API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditLogPublic(BaseModel):
    id: UUID
    timestamp: datetime
    user_id: UUID | None = None
    action: str
    resource_type: str | None = None
    resource_id: UUID | None = None
    status: str
    request_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, row: object) -> AuditLogPublic:
        # The ORM column is ``audit_metadata`` (mapped to DB column
        # ``metadata``) — the public name matches the DB and avoids leaking
        # the SQLAlchemy reserved-word workaround.
        from app.models.audit_log import AuditLog

        assert isinstance(row, AuditLog)
        return cls(
            id=row.id,
            timestamp=row.timestamp,
            user_id=row.user_id,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            status=row.status,
            request_id=row.request_id,
            metadata=dict(row.audit_metadata),
        )


class AuditLogList(BaseModel):
    items: list[AuditLogPublic]
    next_cursor: str | None = None
