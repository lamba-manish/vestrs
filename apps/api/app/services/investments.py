"""Investment service — atomically debit, record, audit.

Per CLAUDE.md sec. 5+9 the invest path:
- runs balance check against the user's active bank account,
- debits the mock_balance, inserts the investment row, and writes the
  ``INVESTMENT_CREATED`` audit row, all in the request's DB transaction
  (success path),
- raises typed ``DomainError``s for every failure mode; failure audits go
  through ``write_independent`` so they survive the rollback.

KYC + accreditation gates live here too: production-shaped behaviour even
though the assignment only requires the balance check. Both must be SUCCESS
before money moves.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from decimal import Decimal

from app.core.errors import DomainError, ErrorCode
from app.core.logging import get_logger
from app.models.accreditation import AccreditationStatus
from app.models.audit_log import AuditAction, AuditStatus
from app.models.investment import Investment
from app.models.kyc import KycStatus
from app.models.user import User
from app.repositories.accreditation import AccreditationRepository
from app.repositories.audit_logs import AuditLogRepository
from app.repositories.bank import BankRepository
from app.repositories.investments import InvestmentRepository
from app.repositories.kyc import KycRepository
from app.services.auth import RequestContext

log = get_logger("api.investments")


def _now() -> datetime:
    return datetime.now(UTC)


def _escrow_ref() -> str:
    return f"escrow-{secrets.token_hex(8)}"


def _domain_error(code: ErrorCode, message: str, *, status: int) -> DomainError:
    err = DomainError(message)
    err.code = code
    err.http_status = status
    return err


class InvestmentService:
    def __init__(
        self,
        investments: InvestmentRepository,
        bank: BankRepository,
        kyc: KycRepository,
        accreditation: AccreditationRepository,
        audit: AuditLogRepository,
    ) -> None:
        self.investments = investments
        self.bank = bank
        self.kyc = kyc
        self.accreditation = accreditation
        self.audit = audit

    async def create(
        self,
        *,
        user: User,
        amount: Decimal,
        notes: str | None,
        idempotency_key: str,
        ctx: RequestContext,
    ) -> Investment:
        await self._enforce_gates(user=user, amount=amount, ctx=ctx)
        bank_account = await self.bank.active_for_user(user.id)
        if bank_account is None:
            await self._block_audit(user=user, reason="no_bank_linked", ctx=ctx)
            raise _domain_error(
                ErrorCode.BANK_NOT_LINKED,
                "Link a bank account before investing.",
                status=409,
            )

        if amount > bank_account.mock_balance:
            await AuditLogRepository.write_independent(
                action=AuditAction.INVESTMENT_FAILED,
                status=AuditStatus.FAILURE,
                user_id=user.id,
                request_id=ctx.request_id,
                ip=ctx.ip,
                user_agent=ctx.user_agent,
                metadata={
                    "reason": "insufficient_balance",
                    "amount": str(amount),
                    "currency": bank_account.currency,
                    "available": str(bank_account.mock_balance),
                    "idempotency_key": idempotency_key,
                },
            )
            raise _domain_error(
                ErrorCode.INSUFFICIENT_BALANCE,
                "Insufficient balance for this investment.",
                status=400,
            )

        investment = await self.investments.create(
            user_id=user.id,
            bank_account=bank_account,
            amount=amount,
            currency=bank_account.currency,
            escrow_reference=_escrow_ref(),
            notes=notes,
            settled_at=_now(),
            raw_response={
                "law_firm_pool": "vestrs-law-firm-pool-001",
                "idempotency_key": idempotency_key,
            },
        )
        await self.audit.write(
            action=AuditAction.INVESTMENT_CREATED,
            status=AuditStatus.SUCCESS,
            user_id=user.id,
            resource_type="investment",
            resource_id=investment.id,
            request_id=ctx.request_id,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
            metadata={
                "amount": str(amount),
                "currency": bank_account.currency,
                "escrow_reference": investment.escrow_reference,
                "idempotency_key": idempotency_key,
            },
        )
        return investment

    async def list_for_user(self, user: User, *, limit: int = 50) -> list[Investment]:
        return await self.investments.list_for_user(user.id, limit=limit)

    # ---- gates --------------------------------------------------------

    async def _enforce_gates(self, *, user: User, amount: Decimal, ctx: RequestContext) -> None:
        kyc_latest = await self.kyc.latest_for_user(user.id)
        if kyc_latest is None or kyc_latest.status != KycStatus.SUCCESS.value:
            await self._block_audit(user=user, reason="kyc_not_passed", ctx=ctx)
            raise _domain_error(
                ErrorCode.KYC_FAILED,
                "Complete KYC before investing.",
                status=409,
            )

        acc_latest = await self.accreditation.latest_for_user(user.id)
        if acc_latest is None or acc_latest.status != AccreditationStatus.SUCCESS.value:
            await self._block_audit(user=user, reason="accreditation_not_passed", ctx=ctx)
            raise _domain_error(
                ErrorCode.ACCREDITATION_FAILED,
                "Complete accreditation before investing.",
                status=409,
            )

        if amount <= 0:
            raise _domain_error(
                ErrorCode.VALIDATION_ERROR,
                "Amount must be positive.",
                status=422,
            )

    async def _block_audit(self, *, user: User, reason: str, ctx: RequestContext) -> None:
        await AuditLogRepository.write_independent(
            action=AuditAction.INVESTMENT_BLOCKED,
            status=AuditStatus.FAILURE,
            user_id=user.id,
            request_id=ctx.request_id,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
            metadata={"reason": reason},
        )
