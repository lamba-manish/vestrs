"""KYC endpoints — submit, retry, status."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import (
    CurrentUserDep,
    KycServiceDep,
    RequestCtxDep,
    SessionDep,
)
from app.core.envelope import success_envelope
from app.core.rate_limit import limit
from app.repositories.kyc import KycRepository
from app.schemas.kyc import KycCheckPublic, KycSummary
from app.services.kyc import summarize

router = APIRouter(prefix="/kyc", tags=["kyc"])


@router.get(
    "",
    summary="Get the current KYC status for the authenticated user",
)
async def get_status(
    request: Request,
    user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, object]:
    repo = KycRepository(session)
    latest = await repo.latest_for_user(user.id)
    used = await repo.attempt_count(user.id)
    status, used, remaining, latest_row = summarize(latest, used)
    payload = KycSummary(
        status=status,
        attempts_used=used,
        attempts_remaining=remaining,
        latest=KycCheckPublic.model_validate(latest_row) if latest_row else None,
    )
    return success_envelope(payload.model_dump(mode="json"), request_id=request.state.request_id)


@router.post(
    "",
    status_code=201,
    summary="Submit the first KYC check for the authenticated user",
    dependencies=[Depends(limit(times=20, seconds=3600, bucket="kyc:submit"))],
)
async def submit(
    request: Request,
    user: CurrentUserDep,
    service: KycServiceDep,
    ctx: RequestCtxDep,
) -> dict[str, object]:
    check = await service.submit(user=user, ctx=ctx)
    return success_envelope(
        KycCheckPublic.model_validate(check).model_dump(mode="json"),
        request_id=request.state.request_id,
    )


@router.post(
    "/retry",
    status_code=201,
    summary="Retry KYC after a failed attempt (subject to retry cap)",
    dependencies=[Depends(limit(times=20, seconds=3600, bucket="kyc:retry"))],
)
async def retry(
    request: Request,
    user: CurrentUserDep,
    service: KycServiceDep,
    ctx: RequestCtxDep,
) -> dict[str, object]:
    check = await service.retry(user=user, ctx=ctx)
    return success_envelope(
        KycCheckPublic.model_validate(check).model_dump(mode="json"),
        request_id=request.state.request_id,
    )
