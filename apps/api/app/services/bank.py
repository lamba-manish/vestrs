"""Bank linking service.

Atomicity rules match every other slice: SUCCESS audits go in the request
session along with the row insert / mutation; FAILURE audits go through
``write_independent`` so they survive ``ConflictError`` rollbacks.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.adapters.bank import BankProvider
from app.core.errors import ConflictError, DomainError, ErrorCode
from app.core.logging import get_logger
from app.models.audit_log import AuditAction, AuditStatus
from app.models.bank import BankAccount
from app.models.user import User
from app.repositories.audit_logs import AuditLogRepository
from app.repositories.bank import BankRepository
from app.services.auth import RequestContext

log = get_logger("api.bank")


def _now() -> datetime:
    return datetime.now(UTC)


class BankService:
    def __init__(
        self,
        bank: BankRepository,
        audit: AuditLogRepository,
        provider: BankProvider,
    ) -> None:
        self.bank = bank
        self.audit = audit
        self.provider = provider

    async def link(
        self,
        *,
        user: User,
        bank_name: str,
        account_holder_name: str,
        account_type: str,
        account_number: str,
        routing_number: str,
        currency: str,
        ctx: RequestContext,
    ) -> BankAccount:
        existing = await self.bank.active_for_user(user.id)
        if existing is not None:
            await AuditLogRepository.write_independent(
                action=AuditAction.BANK_LINK_BLOCKED,
                status=AuditStatus.FAILURE,
                user_id=user.id,
                request_id=ctx.request_id,
                ip=ctx.ip,
                user_agent=ctx.user_agent,
                metadata={"reason": "already_linked"},
            )
            raise ConflictError(
                "A bank account is already linked. Unlink it before linking another."
            )

        result = await self.provider.link_account(
            email=user.email,
            bank_name=bank_name,
            account_holder_name=account_holder_name,
            account_number=account_number,
            routing_number=routing_number,
            currency=currency,
        )

        if not result.success:
            await AuditLogRepository.write_independent(
                action=AuditAction.BANK_LINK_FAILED,
                status=AuditStatus.FAILURE,
                user_id=user.id,
                request_id=ctx.request_id,
                ip=ctx.ip,
                user_agent=ctx.user_agent,
                metadata={
                    "reason": result.failure_reason or "unknown",
                    "provider": self.provider.name,
                },
            )
            err = DomainError("Bank linking failed. Please verify your details and try again.")
            err.code = ErrorCode.BANK_LINK_FAILED
            err.http_status = 400
            raise err

        account = await self.bank.create(
            user_id=user.id,
            bank_name=bank_name,
            account_holder_name=account_holder_name,
            account_type=account_type,
            last_four=result.last_four,
            currency=currency,
            mock_balance=result.mock_balance,
            provider_name=self.provider.name,
            provider_account_id=result.provider_account_id,
            linked_at=_now(),
            raw_response=result.raw,
        )
        await self.audit.write(
            action=AuditAction.BANK_LINKED,
            status=AuditStatus.SUCCESS,
            user_id=user.id,
            resource_type="bank_account",
            resource_id=account.id,
            request_id=ctx.request_id,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
            metadata={
                "provider": self.provider.name,
                "bank_name": bank_name,
                "currency": currency,
                "last_four": result.last_four,
            },
        )
        return account

    async def unlink(self, *, user: User, ctx: RequestContext) -> BankAccount:
        existing = await self.bank.active_for_user(user.id)
        if existing is None:
            err = DomainError("No bank account is currently linked.")
            err.code = ErrorCode.BANK_NOT_LINKED
            err.http_status = 409
            raise err

        await self.provider.unlink_account(provider_account_id=existing.provider_account_id)
        unlinked = await self.bank.mark_unlinked(account=existing, now=_now())
        await self.audit.write(
            action=AuditAction.BANK_UNLINKED,
            status=AuditStatus.SUCCESS,
            user_id=user.id,
            resource_type="bank_account",
            resource_id=existing.id,
            request_id=ctx.request_id,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
            metadata={
                "provider": self.provider.name,
                "last_four": existing.last_four,
            },
        )
        return unlinked
