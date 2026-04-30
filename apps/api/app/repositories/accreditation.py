"""Accreditation repository — DB access only."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accreditation import AccreditationCheck, AccreditationStatus


class AccreditationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, check_id: UUID) -> AccreditationCheck | None:
        return await self.session.get(AccreditationCheck, check_id)

    async def latest_for_user(self, user_id: UUID) -> AccreditationCheck | None:
        result = await self.session.execute(
            select(AccreditationCheck)
            .where(AccreditationCheck.user_id == user_id)
            .order_by(desc(AccreditationCheck.attempt_number))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def attempt_count(self, user_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(AccreditationCheck)
            .where(AccreditationCheck.user_id == user_id)
        )
        return int(result.scalar_one())

    async def create(
        self,
        *,
        user_id: UUID,
        attempt_number: int,
        status: AccreditationStatus,
        provider_name: str,
        provider_reference: str,
        requested_at: datetime,
        raw_response: dict[str, Any],
    ) -> AccreditationCheck:
        check = AccreditationCheck(
            user_id=user_id,
            attempt_number=attempt_number,
            status=status.value,
            provider_name=provider_name,
            provider_reference=provider_reference,
            requested_at=requested_at,
            raw_response=raw_response,
        )
        self.session.add(check)
        await self.session.flush()
        return check

    async def mark_resolved(
        self,
        *,
        check: AccreditationCheck,
        status: AccreditationStatus,
        failure_reason: str | None,
        resolved_at: datetime,
        raw_response: dict[str, Any],
    ) -> AccreditationCheck:
        check.status = status.value
        check.failure_reason = failure_reason
        check.resolved_at = resolved_at
        check.raw_response = raw_response
        await self.session.flush()
        return check
