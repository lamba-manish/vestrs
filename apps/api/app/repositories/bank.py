"""Bank account repository — DB access only."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bank import BankAccount, BankAccountStatus


class BankRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def active_for_user(self, user_id: UUID) -> BankAccount | None:
        result = await self.session.execute(
            select(BankAccount).where(
                BankAccount.user_id == user_id,
                BankAccount.status == BankAccountStatus.ACTIVE.value,
            )
        )
        return result.scalar_one_or_none()

    async def get_for_user(self, user_id: UUID, account_id: UUID) -> BankAccount | None:
        result = await self.session.execute(
            select(BankAccount).where(BankAccount.id == account_id, BankAccount.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        user_id: UUID,
        bank_name: str,
        account_holder_name: str,
        account_type: str,
        last_four: str,
        currency: str,
        mock_balance: Decimal,
        provider_name: str,
        provider_account_id: str,
        linked_at: datetime,
        raw_response: dict[str, Any],
    ) -> BankAccount:
        account = BankAccount(
            user_id=user_id,
            bank_name=bank_name,
            account_holder_name=account_holder_name,
            account_type=account_type,
            last_four=last_four,
            currency=currency,
            mock_balance=mock_balance,
            provider_name=provider_name,
            provider_account_id=provider_account_id,
            linked_at=linked_at,
            raw_response=raw_response,
        )
        self.session.add(account)
        await self.session.flush()
        return account

    async def mark_unlinked(self, *, account: BankAccount, now: datetime) -> BankAccount:
        account.status = BankAccountStatus.UNLINKED.value
        account.unlinked_at = now
        await self.session.flush()
        return account
