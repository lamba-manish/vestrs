"""Investment repository — DB access only."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bank import BankAccount
from app.models.investment import Investment, InvestmentStatus


class InvestmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: UUID, *, limit: int = 50) -> list[Investment]:
        result = await self.session.execute(
            select(Investment)
            .where(Investment.user_id == user_id)
            .order_by(desc(Investment.created_at))
            .limit(limit)
        )
        return list(result.scalars())

    async def create(
        self,
        *,
        user_id: UUID,
        bank_account: BankAccount,
        amount: Decimal,
        currency: str,
        escrow_reference: str,
        notes: str | None,
        settled_at: datetime,
        raw_response: dict[str, Any],
    ) -> Investment:
        # Atomically debit the linked bank's mock balance and record the
        # investment row. The caller's session commits on success.
        bank_account.mock_balance = bank_account.mock_balance - amount

        investment = Investment(
            user_id=user_id,
            bank_account_id=bank_account.id,
            amount=amount,
            currency=currency,
            status=InvestmentStatus.SETTLED.value,
            escrow_reference=escrow_reference,
            notes=notes,
            settled_at=settled_at,
            raw_response=raw_response,
        )
        self.session.add(investment)
        await self.session.flush()
        return investment
