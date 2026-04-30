"""KYC repository — DB access only."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kyc import KycCheck, KycStatus


class KycRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def latest_for_user(self, user_id: UUID) -> KycCheck | None:
        result = await self.session.execute(
            select(KycCheck)
            .where(KycCheck.user_id == user_id)
            .order_by(desc(KycCheck.attempt_number))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def attempt_count(self, user_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(KycCheck).where(KycCheck.user_id == user_id)
        )
        return int(result.scalar_one())

    async def create(
        self,
        *,
        user_id: UUID,
        attempt_number: int,
        status: KycStatus,
        provider_name: str,
        provider_reference: str,
        failure_reason: str | None,
        requested_at: datetime,
        resolved_at: datetime | None,
        raw_response: dict[str, Any],
    ) -> KycCheck:
        check = KycCheck(
            user_id=user_id,
            attempt_number=attempt_number,
            status=status.value,
            provider_name=provider_name,
            provider_reference=provider_reference,
            failure_reason=failure_reason,
            requested_at=requested_at,
            resolved_at=resolved_at,
            raw_response=raw_response,
        )
        self.session.add(check)
        await self.session.flush()
        return check
