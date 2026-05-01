"""Accreditation service.

Submit creates a pending row + writes the SUBMITTED audit in the request
session, then enqueues an ARQ job that fires after the configured delay.

Resolution lives in ``resolve_check`` — invoked by the worker (or directly
in tests). It opens its own DB session, polls the adapter, and either
flips the row to SUCCESS/FAILED + writes a RESOLVED audit, or leaves the
row PENDING and re-enqueues the job (caller's responsibility — the worker
handles the re-enqueue using the function's return value).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.adapters.accreditation import AccreditationProvider
from app.core.config import Settings
from app.core.errors import ConflictError, DomainError, ErrorCode
from app.core.logging import get_logger
from app.db.session import get_session_factory
from app.models.accreditation import AccreditationCheck, AccreditationStatus
from app.models.audit_log import AuditAction, AuditStatus
from app.models.user import User
from app.repositories.accreditation import AccreditationRepository
from app.repositories.audit_logs import AuditLogRepository
from app.schemas.accreditation import (
    IncomeAccreditation,
    NetWorthAccreditation,
    ProfessionalCertAccreditation,
    evaluate_path_outcome,
    serialise_path_data,
)
from app.services.auth import RequestContext

log = get_logger("api.accreditation")


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class SubmitOutcome:
    check: AccreditationCheck
    enqueue_after_seconds: int


def _audit_status_for(status: AccreditationStatus) -> str:
    if status is AccreditationStatus.SUCCESS:
        return AuditStatus.SUCCESS
    if status is AccreditationStatus.FAILED:
        return AuditStatus.FAILURE
    return AuditStatus.PENDING


# ---------------------------------------------------------------------------
# Service used from request handlers (atomic-with-request-tx)
# ---------------------------------------------------------------------------


class AccreditationService:
    def __init__(
        self,
        accreditation: AccreditationRepository,
        audit: AuditLogRepository,
        provider: AccreditationProvider,
        settings: Settings,
    ) -> None:
        self.accreditation = accreditation
        self.audit = audit
        self.provider = provider
        self.settings = settings

    async def submit(
        self,
        *,
        user: User,
        ctx: RequestContext,
        body: IncomeAccreditation | NetWorthAccreditation | ProfessionalCertAccreditation,
    ) -> SubmitOutcome:
        latest = await self.accreditation.latest_for_user(user.id)
        if latest is not None and not latest.is_terminal:
            await AuditLogRepository.write_independent(
                action=AuditAction.ACCREDITATION_RETRY_BLOCKED,
                status=AuditStatus.FAILURE,
                user_id=user.id,
                request_id=ctx.request_id,
                ip=ctx.ip,
                user_agent=ctx.user_agent,
                metadata={"reason": "in_flight"},
            )
            raise ConflictError("An accreditation review is already in progress.")

        if latest is not None and latest.status == AccreditationStatus.SUCCESS.value:
            await AuditLogRepository.write_independent(
                action=AuditAction.ACCREDITATION_RETRY_BLOCKED,
                status=AuditStatus.FAILURE,
                user_id=user.id,
                request_id=ctx.request_id,
                ip=ctx.ip,
                user_agent=ctx.user_agent,
                metadata={"reason": "already_succeeded"},
            )
            raise ConflictError("Accreditation already verified.")

        delay = self.settings.accreditation_resolution_delay_seconds
        attempt_number = (
            (await self.accreditation.attempt_count(user.id)) + 1 if latest is not None else 1
        )

        passes, failure_reason = evaluate_path_outcome(body)
        path_data = serialise_path_data(body)

        result = await self.provider.submit_check(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            nationality=user.nationality,
            domicile=user.domicile,
            delay_seconds=delay,
            path=body.path,
            path_passes_sec=passes,
            path_failure_reason=failure_reason,
            path_data=path_data,
        )
        check = await self.accreditation.create(
            user_id=user.id,
            attempt_number=attempt_number,
            status=result.status,
            provider_name=self.provider.name,
            provider_reference=result.provider_reference,
            requested_at=_now(),
            raw_response=result.raw,
            path=body.path,
            path_data=path_data,
        )
        await self.audit.write(
            action=AuditAction.ACCREDITATION_SUBMITTED,
            status=_audit_status_for(result.status),
            user_id=user.id,
            resource_type="accreditation_check",
            resource_id=check.id,
            request_id=ctx.request_id,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
            metadata={
                "attempt_number": attempt_number,
                "provider_status": result.status.value,
                "provider": self.provider.name,
                "delay_seconds": delay,
                "path": body.path,
                "path_passes_sec": passes,
            },
        )

        # On the off-chance the vendor returned a terminal status synchronously
        # we still emit the resolved audit so the audit log is consistent.
        if check.is_terminal:
            await self._audit_resolved(check, ctx_kind="sync")
            return SubmitOutcome(check=check, enqueue_after_seconds=0)

        # Real flow: pending — caller will enqueue the worker job.
        return SubmitOutcome(check=check, enqueue_after_seconds=delay)

    async def _audit_resolved(self, check: AccreditationCheck, *, ctx_kind: str) -> None:
        await self.audit.write(
            action=AuditAction.ACCREDITATION_RESOLVED,
            status=_audit_status_for(AccreditationStatus(check.status)),
            user_id=check.user_id,
            resource_type="accreditation_check",
            resource_id=check.id,
            metadata={
                "provider_status": check.status,
                "provider": check.provider_name,
                "ctx": ctx_kind,
            },
        )


# ---------------------------------------------------------------------------
# Worker-side resolution (own session, own commit)
# ---------------------------------------------------------------------------


async def resolve_check(
    *,
    check_id: UUID,
    provider: AccreditationProvider,
) -> tuple[AccreditationStatus, bool]:
    """Poll the vendor for a check and either flip its status terminally or
    leave it pending. Returns ``(status, terminal)`` so the worker can decide
    whether to re-enqueue.

    Opens its own DB session and commits independently of any request session.
    """
    factory = get_session_factory()
    async with factory() as session:
        repo = AccreditationRepository(session)
        check = await repo.get(check_id)
        if check is None:
            log.warning("accreditation_resolve_unknown_check", check_id=str(check_id))
            return AccreditationStatus.NOT_STARTED, True

        if check.is_terminal:
            return AccreditationStatus(check.status), True

        if check.provider_reference is None:
            log.warning("accreditation_resolve_no_provider_ref", check_id=str(check_id))
            return AccreditationStatus(check.status), False

        result = await provider.fetch_status(provider_reference=check.provider_reference)
        if result.status not in {AccreditationStatus.SUCCESS, AccreditationStatus.FAILED}:
            return result.status, False

        await repo.mark_resolved(
            check=check,
            status=result.status,
            failure_reason=result.failure_reason,
            resolved_at=_now(),
            raw_response=result.raw,
        )

        audit_meta: dict[str, Any] = {
            "provider_status": result.status.value,
            "provider": check.provider_name,
            "ctx": "worker",
        }
        await AuditLogRepository(session).write(
            action=AuditAction.ACCREDITATION_RESOLVED,
            status=_audit_status_for(result.status),
            user_id=check.user_id,
            resource_type="accreditation_check",
            resource_id=check.id,
            metadata=audit_meta,
        )
        await session.commit()
        log.info(
            "accreditation_resolved",
            check_id=str(check.id),
            status=result.status.value,
        )
        return result.status, True


def _refresh_required(message: str) -> DomainError:
    err = DomainError(message)
    err.code = ErrorCode.ACCREDITATION_PENDING
    err.http_status = 409
    return err
