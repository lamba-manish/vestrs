"""Accreditation endpoints — submit, current status."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import (
    AccreditationServiceDep,
    CurrentUserDep,
    RequestCtxDep,
    SessionDep,
)
from app.core.envelope import success_envelope
from app.core.rate_limit import limit
from app.models.accreditation import AccreditationStatus
from app.repositories.accreditation import AccreditationRepository
from app.schemas.accreditation import AccreditationCheckPublic, AccreditationSummary
from app.workers import enqueue_accreditation_resolve

router = APIRouter(prefix="/accreditation", tags=["accreditation"])


@router.get(
    "",
    summary="Get the current accreditation status for the authenticated user",
)
async def get_status(
    request: Request,
    user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, object]:
    repo = AccreditationRepository(session)
    latest = await repo.latest_for_user(user.id)
    payload = AccreditationSummary(
        status=latest.status if latest else AccreditationStatus.NOT_STARTED.value,
        latest=AccreditationCheckPublic.model_validate(latest) if latest else None,
    )
    return success_envelope(payload.model_dump(mode="json"), request_id=request.state.request_id)


@router.post(
    "",
    status_code=202,
    summary="Submit an accreditation review (async — resolves later)",
    dependencies=[Depends(limit(times=10, seconds=3600, bucket="accreditation:submit"))],
)
async def submit(
    request: Request,
    user: CurrentUserDep,
    service: AccreditationServiceDep,
    ctx: RequestCtxDep,
) -> dict[str, object]:
    outcome = await service.submit(user=user, ctx=ctx)
    if outcome.enqueue_after_seconds > 0:
        await enqueue_accreditation_resolve(
            outcome.check.id, defer_seconds=outcome.enqueue_after_seconds
        )
    return success_envelope(
        AccreditationCheckPublic.model_validate(outcome.check).model_dump(mode="json"),
        request_id=request.state.request_id,
    )
