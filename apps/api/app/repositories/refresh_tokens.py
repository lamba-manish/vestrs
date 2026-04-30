"""Refresh-token repository.

Holds the queries that implement rotation + reuse detection, but never the
policy itself — that lives in the auth service.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        token_id: UUID,
        user_id: UUID,
        token_hash: str,
        family_id: UUID,
        expires_at: datetime,
        user_agent: str | None,
        ip: str | None,
    ) -> RefreshToken:
        token = RefreshToken(
            id=token_id,
            user_id=user_id,
            token_hash=token_hash,
            family_id=family_id,
            expires_at=expires_at,
            user_agent=user_agent,
            ip=ip,
        )
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_by_id(self, token_id: UUID) -> RefreshToken | None:
        return await self.session.get(RefreshToken, token_id)

    async def mark_replaced(self, *, token_id: UUID, replacement_id: UUID, now: datetime) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.id == token_id)
            .values(replaced_by_id=replacement_id, updated_at=now)
        )

    async def revoke(self, *, token_id: UUID, now: datetime) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.id == token_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now, updated_at=now)
        )

    async def revoke_family(self, *, family_id: UUID, now: datetime) -> int:
        """Revoke every token in a family. Returns the row count revoked."""
        result = await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now, updated_at=now)
        )
        # Result.rowcount is dialect-specific and typed loosely; cast to int.
        return int(getattr(result, "rowcount", 0) or 0)

    async def list_active_for_user(self, user_id: UUID) -> list[RefreshToken]:
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        return list(result.scalars())
