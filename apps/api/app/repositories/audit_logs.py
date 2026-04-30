"""Audit-log repository.

Per CLAUDE.md sec. 9, audit writes for **successful** state changes happen
in the same DB transaction as the action they describe — same ``AsyncSession``,
no commit here, the request's get_session() dependency commits at the end.

Audit writes for **failures** must persist even when the action's transaction
rolls back (otherwise we lose the record that an attempt was made). Those go
through ``write_independent`` which opens its own short-lived session and
commits immediately.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_factory
from app.models.audit_log import AuditLog


def _build(
    *,
    action: str,
    status: str,
    user_id: UUID | None,
    resource_type: str | None,
    resource_id: UUID | None,
    request_id: str | None,
    ip: str | None,
    user_agent: str | None,
    metadata: dict[str, Any] | None,
) -> AuditLog:
    return AuditLog(
        user_id=user_id,
        action=action,
        status=status,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        ip=ip,
        user_agent=user_agent,
        audit_metadata=metadata or {},
    )


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def write(
        self,
        *,
        action: str,
        status: str,
        user_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        request_id: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Write atomically with the request's session (use for SUCCESS audits)."""
        entry = _build(
            action=action,
            status=status,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
            metadata=metadata,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    @staticmethod
    async def write_independent(
        *,
        action: str,
        status: str,
        user_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        request_id: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Write in a fresh session that commits immediately.

        Used for FAILURE audits so the row survives the action's rollback.
        """
        factory = get_session_factory()
        async with factory() as session:
            entry = _build(
                action=action,
                status=status,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                metadata=metadata,
            )
            session.add(entry)
            await session.commit()
