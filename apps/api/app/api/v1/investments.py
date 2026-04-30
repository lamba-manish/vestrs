"""Investment endpoints — list and create-with-idempotency."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse

from app.api.deps import (
    CurrentUserDep,
    IdempotencyStoreDep,
    InvestmentServiceDep,
    RequestCtxDep,
)
from app.core.envelope import error_envelope, success_envelope
from app.core.errors import DomainError, ErrorCode
from app.core.idempotency import hash_body
from app.core.rate_limit import limit
from app.models.audit_log import AuditAction, AuditStatus
from app.repositories.audit_logs import AuditLogRepository
from app.schemas.investments import (
    InvestmentCreateRequest,
    InvestmentList,
    InvestmentPublic,
)

router = APIRouter(prefix="/investments", tags=["investments"])


def _idempotency_key_invalid() -> DomainError:
    err = DomainError(
        "Idempotency-Key header is required, 8-128 chars, ASCII printable.",
    )
    err.code = ErrorCode.VALIDATION_ERROR
    err.http_status = 422
    return err


@router.get(
    "",
    summary="List the authenticated user's recent investments",
)
async def list_investments(
    request: Request,
    user: CurrentUserDep,
    service: InvestmentServiceDep,
) -> dict[str, object]:
    rows = await service.list_for_user(user)
    payload = InvestmentList(
        items=[InvestmentPublic.model_validate(r) for r in rows],
        total=len(rows),
    )
    return success_envelope(payload.model_dump(mode="json"), request_id=request.state.request_id)


@router.post(
    "",
    status_code=201,
    summary="Create an investment (Idempotency-Key required)",
    dependencies=[Depends(limit(times=20, seconds=300, bucket="invest:create"))],
)
async def create_investment(
    body: InvestmentCreateRequest,
    request: Request,
    user: CurrentUserDep,
    service: InvestmentServiceDep,
    store: IdempotencyStoreDep,
    ctx: RequestCtxDep,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
) -> JSONResponse:
    body_dump = body.model_dump(mode="json")
    body_hash = hash_body(body_dump)

    # 1. Replay check.
    cached = await store.get(user.id, idempotency_key)
    if cached is not None:
        if cached.body_hash != body_hash:
            await AuditLogRepository.write_independent(
                action=AuditAction.INVESTMENT_BLOCKED,
                status=AuditStatus.FAILURE,
                user_id=user.id,
                request_id=ctx.request_id,
                ip=ctx.ip,
                user_agent=ctx.user_agent,
                metadata={
                    "reason": "idempotency_key_reused",
                    "idempotency_key": idempotency_key,
                },
            )
            payload = error_envelope(
                ErrorCode.IDEMPOTENCY_KEY_REUSED,
                "This Idempotency-Key was used with a different request body.",
                request_id=request.state.request_id,
            )
            return JSONResponse(payload, status_code=409)

        # Same key + same body — replay the cached response.
        await AuditLogRepository.write_independent(
            action=AuditAction.INVESTMENT_IDEMPOTENT_REPLAY,
            status=AuditStatus.SUCCESS,
            user_id=user.id,
            request_id=ctx.request_id,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
            metadata={"idempotency_key": idempotency_key},
        )
        return JSONResponse(cached.response, status_code=cached.status_code)

    # 2. Fresh request — execute.
    investment = await service.create(
        user=user,
        amount=body.amount,
        notes=body.notes,
        idempotency_key=idempotency_key,
        ctx=ctx,
    )

    response = success_envelope(
        InvestmentPublic.model_validate(investment).model_dump(mode="json"),
        request_id=request.state.request_id,
    )

    # 3. Persist for replay (24h TTL). The store survives the request session
    # because it has its own Redis pipeline — no impact on the action's tx.
    await store.store(
        user.id,
        idempotency_key,
        body_hash=body_hash,
        status_code=201,
        response=response,
    )
    return JSONResponse(response, status_code=201)
