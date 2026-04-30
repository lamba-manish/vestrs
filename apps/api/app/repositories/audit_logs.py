"""Audit-log repository.

Per CLAUDE.md sec. 9, audit writes for **successful** state changes happen
in the same DB transaction as the action they describe — same ``AsyncSession``,
no commit here, the request's get_session() dependency commits at the end.

Audit writes for **failures** must persist even when the action's transaction
rolls back (otherwise we lose the record that an attempt was made). Those go
through ``write_independent`` which opens its own short-lived session and
commits immediately.

Reads use cursor pagination keyed on ``id`` (UUIDv6 → time-sortable, so
``ORDER BY id DESC`` ≡ newest-first without needing the timestamp column).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
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

    async def list_paginated(
        self,
        *,
        user_id: UUID | None,
        action: str | None,
        since: datetime | None,
        until: datetime | None,
        before_id: UUID | None,
        limit: int,
    ) -> list[AuditLog]:
        """Newest-first page of audit rows.

        ``user_id=None`` means "every user" (admin-only at the route layer).
        ``before_id`` is the cursor: only rows with ``id < before_id`` are
        returned. ``limit`` is bounded by the route.
        """
        stmt = select(AuditLog).order_by(desc(AuditLog.id)).limit(limit)
        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        if since is not None:
            stmt = stmt.where(AuditLog.timestamp >= since)
        if until is not None:
            stmt = stmt.where(AuditLog.timestamp < until)
        if before_id is not None:
            stmt = stmt.where(AuditLog.id < before_id)
        result = await self.session.execute(stmt)
        return list(result.scalars())

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
