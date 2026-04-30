"""FastAPI dependencies — DB session, request context, auth."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError, ErrorCode
from app.core.security import ACCESS_COOKIE, REFRESH_COOKIE, TokenType, decode_token
from app.db.session import get_session
from app.models.user import User
from app.repositories.audit_logs import AuditLogRepository
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository
from app.services.auth import AuthService, RequestContext


async def db_session() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(db_session)]


def request_context(request: Request) -> RequestContext:
    forwarded = request.headers.get("x-forwarded-for")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    return RequestContext(
        request_id=getattr(request.state, "request_id", None),
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )


RequestCtxDep = Annotated[RequestContext, Depends(request_context)]


def auth_service(session: SessionDep) -> AuthService:
    return AuthService(
        users=UserRepository(session),
        refresh_tokens=RefreshTokenRepository(session),
        audit=AuditLogRepository(session),
    )


AuthServiceDep = Annotated[AuthService, Depends(auth_service)]


async def current_user(
    request: Request,
    session: SessionDep,
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> User:
    if access_token is None:
        err = DomainError("Authentication required.")
        err.code = ErrorCode.AUTH_TOKEN_INVALID
        err.http_status = 401
        raise err

    payload = decode_token(access_token, expected=TokenType.ACCESS)
    user = await UserRepository(session).get_by_id(payload.sub)
    if user is None:
        err = DomainError("User no longer exists.")
        err.code = ErrorCode.AUTH_TOKEN_INVALID
        err.http_status = 401
        raise err

    request.state.user_id = str(user.id)
    return user


CurrentUserDep = Annotated[User, Depends(current_user)]


async def refresh_cookie(
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> str:
    if not refresh_token:
        err = DomainError("Refresh token missing.")
        err.code = ErrorCode.AUTH_REFRESH_REQUIRED
        err.http_status = 401
        raise err
    return refresh_token


RefreshCookieDep = Annotated[str, Depends(refresh_cookie)]
