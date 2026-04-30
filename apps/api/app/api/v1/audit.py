"""Audit-log read endpoint.

Authorization model:
- Anyone authenticated can read **their own** audit log.
- Admins (token role == ADMIN) can pass ``?user_id=<uuid>`` to scope to a
  specific user, or ``?all=true`` to span every user.
- Non-admins requesting another user's logs get 403 ``FORBIDDEN``.
"""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.deps import (
    SessionDep,
    TokenSubjectDep,
)
from app.core.envelope import success_envelope
from app.core.errors import DomainError, ErrorCode, ForbiddenError
from app.core.security import Role
from app.repositories.audit_logs import AuditLogRepository
from app.schemas.audit import AuditLogList, AuditLogPublic

router = APIRouter(prefix="/audit", tags=["audit"])


def _encode_cursor(audit_id: UUID) -> str:
    return base64.urlsafe_b64encode(str(audit_id).encode("ascii")).decode("ascii")


def _decode_cursor(cursor: str) -> UUID:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii")
        return UUID(raw)
    except (ValueError, TypeError) as exc:
        err = DomainError("Invalid cursor.")
        err.code = ErrorCode.VALIDATION_ERROR
        err.http_status = 422
        raise err from exc


@router.get(
    "",
    summary="List audit-log entries (self by default; admin can widen scope)",
)
async def list_audit(
    request: Request,
    subject: TokenSubjectDep,
    session: SessionDep,
    user_id: Annotated[UUID | None, Query(description="Admin-only.")] = None,
    all_users: Annotated[
        bool, Query(alias="all", description="Admin-only — span every user.")
    ] = False,
    action: Annotated[str | None, Query(max_length=64)] = None,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, object]:
    is_admin = subject.role is Role.ADMIN

    if all_users:
        if not is_admin:
            raise ForbiddenError("Admin role required to view all users' logs.")
        target_user_id: UUID | None = None
    elif user_id is not None and user_id != subject.id:
        if not is_admin:
            raise ForbiddenError("Admin role required to view another user's logs.")
        target_user_id = user_id
    else:
        target_user_id = subject.id

    before_id = _decode_cursor(cursor) if cursor else None
    repo = AuditLogRepository(session)
    rows = await repo.list_paginated(
        user_id=target_user_id,
        action=action,
        since=since,
        until=until,
        before_id=before_id,
        limit=limit,
    )

    items = [AuditLogPublic.from_model(r) for r in rows]
    next_cursor = _encode_cursor(rows[-1].id) if len(rows) == limit else None

    payload = AuditLogList(items=items, next_cursor=next_cursor)
    return success_envelope(payload.model_dump(mode="json"), request_id=request.state.request_id)
