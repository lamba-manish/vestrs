"""Bank linking endpoints — link, unlink, status."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import (
    BankServiceDep,
    CurrentUserDep,
    RequestCtxDep,
    SessionDep,
)
from app.core.envelope import success_envelope
from app.core.rate_limit import limit
from app.repositories.bank import BankRepository
from app.schemas.bank import BankAccountPublic, BankLinkRequest, BankSummary

router = APIRouter(prefix="/bank", tags=["bank"])


@router.get(
    "",
    summary="Return the user's linked bank account, or null",
)
async def get_status(
    request: Request,
    user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, object]:
    repo = BankRepository(session)
    account = await repo.active_for_user(user.id)
    payload = BankSummary(
        linked=account is not None,
        account=BankAccountPublic.model_validate(account) if account else None,
    )
    return success_envelope(payload.model_dump(mode="json"), request_id=request.state.request_id)


@router.post(
    "/link",
    status_code=201,
    summary="Link a bank account (Plaid-like; only masked details persisted)",
    dependencies=[Depends(limit(times=20, seconds=3600, bucket="bank:link"))],
)
async def link(
    body: BankLinkRequest,
    request: Request,
    user: CurrentUserDep,
    service: BankServiceDep,
    ctx: RequestCtxDep,
) -> dict[str, object]:
    account = await service.link(
        user=user,
        bank_name=body.bank_name,
        account_holder_name=body.account_holder_name,
        account_type=body.account_type.value,
        account_number=body.account_number.get_secret_value(),
        routing_number=body.routing_number.get_secret_value(),
        currency=body.currency,
        ctx=ctx,
    )
    return success_envelope(
        BankAccountPublic.model_validate(account).model_dump(mode="json"),
        request_id=request.state.request_id,
    )


@router.delete(
    "",
    summary="Unlink the currently active bank account",
)
async def unlink(
    request: Request,
    user: CurrentUserDep,
    service: BankServiceDep,
    ctx: RequestCtxDep,
) -> dict[str, object]:
    account = await service.unlink(user=user, ctx=ctx)
    return success_envelope(
        BankAccountPublic.model_validate(account).model_dump(mode="json"),
        request_id=request.state.request_id,
    )
