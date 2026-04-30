"""KYC service — orchestrates adapter calls, persistence, and audit logging.

Atomicity: each successful submit/retry writes the kyc_checks row and the
audit row in the same DB transaction (the request session). Failure audits
that are not associated with a state change (retry blocked / exhausted) go
through ``AuditLogRepository.write_independent`` so they survive the
rollback caused by the raised ``ConflictError``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.adapters.kyc import KycCheckResult, KycProvider
from app.core.errors import ConflictError, DomainError, ErrorCode
from app.models.audit_log import AuditAction, AuditStatus
from app.models.kyc import KYC_MAX_ATTEMPTS, KycCheck, KycStatus
from app.models.user import User
from app.repositories.audit_logs import AuditLogRepository
from app.repositories.kyc import KycRepository
from app.services.auth import RequestContext


def _now() -> datetime:
    return datetime.now(UTC)


def _terminal(status: KycStatus) -> bool:
    return status in {KycStatus.SUCCESS, KycStatus.FAILED}


class KycService:
    def __init__(
        self,
        kyc: KycRepository,
        audit: AuditLogRepository,
        provider: KycProvider,
    ) -> None:
        self.kyc = kyc
        self.audit = audit
        self.provider = provider

    # ---- public API ----------------------------------------------------

    async def submit(self, *, user: User, ctx: RequestContext) -> KycCheck:
        latest = await self.kyc.latest_for_user(user.id)
        if latest is not None:
            await self._audit_blocked(
                user.id, ctx, reason="already_started", action=AuditAction.KYC_RETRY_BLOCKED
            )
            raise ConflictError(
                "A KYC check has already been started. Use /kyc/retry if it failed."
            )
        return await self._run_and_persist(user=user, attempt_number=1, ctx=ctx)

    async def retry(self, *, user: User, ctx: RequestContext) -> KycCheck:
        latest = await self.kyc.latest_for_user(user.id)
        if latest is None:
            await self._audit_blocked(
                user.id, ctx, reason="no_prior_attempt", action=AuditAction.KYC_RETRY_BLOCKED
            )
            raise ConflictError("No prior KYC attempt — use /kyc to start.")

        if latest.status == KycStatus.SUCCESS.value:
            await self._audit_blocked(
                user.id, ctx, reason="already_succeeded", action=AuditAction.KYC_RETRY_BLOCKED
            )
            raise ConflictError("KYC already succeeded.")

        if latest.status == KycStatus.PENDING.value:
            await self._audit_blocked(
                user.id, ctx, reason="pending", action=AuditAction.KYC_RETRY_BLOCKED
            )
            raise ConflictError("KYC is still pending — wait for the provider.")

        attempts = await self.kyc.attempt_count(user.id)
        if attempts >= KYC_MAX_ATTEMPTS:
            await self._audit_blocked(
                user.id, ctx, reason="cap_reached", action=AuditAction.KYC_RETRY_EXHAUSTED
            )
            err = DomainError(
                "Retry limit reached. Contact support to continue.",
            )
            err.code = ErrorCode.KYC_RETRY_EXHAUSTED
            err.http_status = 409
            raise err

        return await self._run_and_persist(user=user, attempt_number=attempts + 1, ctx=ctx)

    # ---- internals -----------------------------------------------------

    async def _run_and_persist(
        self, *, user: User, attempt_number: int, ctx: RequestContext
    ) -> KycCheck:
        requested_at = _now()
        result = await self.provider.submit_check(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            nationality=user.nationality,
            domicile=user.domicile,
        )
        resolved_at = requested_at if _terminal(result.status) else None

        check = await self.kyc.create(
            user_id=user.id,
            attempt_number=attempt_number,
            status=result.status,
            provider_name=self.provider.name,
            provider_reference=result.provider_reference,
            failure_reason=result.failure_reason,
            requested_at=requested_at,
            resolved_at=resolved_at,
            raw_response=result.raw,
        )

        await self.audit.write(
            action=AuditAction.KYC_SUBMITTED,
            status=_audit_status_for(result.status),
            user_id=user.id,
            resource_type="kyc_check",
            resource_id=check.id,
            request_id=ctx.request_id,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
            metadata={
                "attempt_number": attempt_number,
                "provider_status": result.status.value,
                "provider": self.provider.name,
            },
        )
        return check

    async def _audit_blocked(
        self,
        user_id: UUID,
        ctx: RequestContext,
        *,
        reason: str,
        action: str,
    ) -> None:
        await AuditLogRepository.write_independent(
            action=action,
            status=AuditStatus.FAILURE,
            user_id=user_id,
            request_id=ctx.request_id,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
            metadata={"reason": reason},
        )


def _audit_status_for(provider_status: KycStatus) -> str:
    if provider_status is KycStatus.SUCCESS:
        return AuditStatus.SUCCESS
    if provider_status is KycStatus.FAILED:
        return AuditStatus.FAILURE
    return AuditStatus.PENDING


# Helper used by GET /kyc to map a (latest, attempts) pair to the API summary.
def summarize(latest: KycCheck | None, attempts_used: int) -> tuple[str, int, int, KycCheck | None]:
    status = latest.status if latest is not None else KycStatus.NOT_STARTED.value
    remaining = max(KYC_MAX_ATTEMPTS - attempts_used, 0)
    return status, attempts_used, remaining, latest


# Re-export for the result type so the route can also wrap pending status.
__all__ = ["KycCheckResult", "KycService", "summarize"]
