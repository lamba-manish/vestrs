"""Auth router: signup, login, refresh, logout, me.

Routes never query the DB or shape error responses — the service does the
work, the dependency-managed session commits on success, the global
exception handler builds the failure envelope.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response

from app.api.deps import (
    AuthServiceDep,
    CurrentUserDep,
    RefreshCookieDep,
    RequestCtxDep,
    TokenSubjectDep,
)
from app.core.envelope import success_envelope
from app.core.rate_limit import limit
from app.core.security import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.schemas.auth import AuthSuccess, LoginRequest, SignupRequest, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


def _envelope(request: Request, payload: AuthSuccess) -> dict[str, object]:
    return success_envelope(payload.model_dump(mode="json"), request_id=request.state.request_id)


@router.post(
    "/signup",
    status_code=201,
    summary="Create an account and start a session",
    dependencies=[Depends(limit(times=10, seconds=3600, bucket="auth:signup"))],
)
async def signup(
    body: SignupRequest,
    request: Request,
    response: Response,
    service: AuthServiceDep,
    ctx: RequestCtxDep,
) -> dict[str, object]:
    result = await service.signup(
        email=body.email,
        password=body.password.get_secret_value(),
        ctx=ctx,
    )
    set_auth_cookies(
        response,
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
        access_expires=result.tokens.access_expires,
        refresh_expires=result.tokens.refresh_expires,
    )
    return _envelope(request, AuthSuccess(user=UserPublic.model_validate(result.user)))


@router.post(
    "/login",
    summary="Sign in with email + password",
    dependencies=[Depends(limit(times=10, seconds=300, bucket="auth:login"))],
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    service: AuthServiceDep,
    ctx: RequestCtxDep,
) -> dict[str, object]:
    result = await service.login(
        email=body.email,
        password=body.password.get_secret_value(),
        ctx=ctx,
    )
    set_auth_cookies(
        response,
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
        access_expires=result.tokens.access_expires,
        refresh_expires=result.tokens.refresh_expires,
    )
    return _envelope(request, AuthSuccess(user=UserPublic.model_validate(result.user)))


@router.post(
    "/refresh",
    summary="Rotate the refresh token, issue a new access token",
    dependencies=[Depends(limit(times=60, seconds=300, bucket="auth:refresh"))],
)
async def refresh(
    request: Request,
    response: Response,
    service: AuthServiceDep,
    ctx: RequestCtxDep,
    refresh_token: RefreshCookieDep,
) -> dict[str, object]:
    result = await service.refresh(refresh_token=refresh_token, ctx=ctx)
    set_auth_cookies(
        response,
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
        access_expires=result.tokens.access_expires,
        refresh_expires=result.tokens.refresh_expires,
    )
    return _envelope(request, AuthSuccess(user=UserPublic.model_validate(result.user)))


@router.post("/logout", summary="Revoke the current refresh token and clear cookies")
async def logout(
    request: Request,
    response: Response,
    service: AuthServiceDep,
    ctx: RequestCtxDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> dict[str, object]:
    await service.logout(refresh_token=refresh_token, ctx=ctx)
    clear_auth_cookies(response)
    return success_envelope({"logged_out": True}, request_id=request.state.request_id)


@router.get(
    "/me",
    summary="Return the authenticated user (from token claims, no DB hit)",
)
async def me(request: Request, subject: TokenSubjectDep) -> dict[str, object]:
    # Identity comes from the access-token claims, not the DB. Profile fields
    # (slice 5+) will live behind their own endpoint that does hit the DB.
    return success_envelope(
        {"id": str(subject.id), "email": subject.email},
        request_id=request.state.request_id,
    )


@router.get(
    "/profile",
    summary="Return the authenticated user's full profile (DB-fresh)",
)
async def profile(request: Request, user: CurrentUserDep) -> dict[str, object]:
    return success_envelope(
        UserPublic.model_validate(user).model_dump(mode="json"),
        request_id=request.state.request_id,
    )
