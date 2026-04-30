"""FastAPI dependencies — DB session, request context, auth.

Two flavours of "who's calling":

- ``TokenSubjectDep`` — derived purely from the access-cookie JWT. No DB
  hit. Carries id, email, role. Use this when the route only needs to
  authorize or to identify the caller (most endpoints).
- ``CurrentUserDep`` — loads the User row. Use only when fresh DB-side
  fields are needed (profile editing, anything dependent on flags that
  may have changed since the access token was issued).

Authorization for role-gated routes uses the ``RoleRequired`` factory:

    admin = Depends(RoleRequired(Role.ADMIN))
    @router.get("/admin/foo", dependencies=[admin])
    async def foo(): ...
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.accreditation import (
    AccreditationProvider,
    MockAccreditationAdapter,
)
from app.adapters.kyc import KycProvider, MockKycAdapter
from app.core.config import Settings, get_settings
from app.core.errors import DomainError, ErrorCode, ForbiddenError
from app.core.security import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    Role,
    TokenType,
    decode_token,
)
from app.db.session import get_session
from app.models.user import User
from app.repositories.accreditation import AccreditationRepository
from app.repositories.audit_logs import AuditLogRepository
from app.repositories.kyc import KycRepository
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository
from app.services.accreditation import AccreditationService
from app.services.auth import AuthService, RequestContext
from app.services.kyc import KycService
from app.services.users import UserService

# ---- DB session -----------------------------------------------------------


async def db_session() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(db_session)]


# ---- request context ------------------------------------------------------


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


# ---- service factories ----------------------------------------------------


def auth_service(session: SessionDep) -> AuthService:
    return AuthService(
        users=UserRepository(session),
        refresh_tokens=RefreshTokenRepository(session),
        audit=AuditLogRepository(session),
    )


AuthServiceDep = Annotated[AuthService, Depends(auth_service)]


def user_service(session: SessionDep) -> UserService:
    return UserService(
        users=UserRepository(session),
        audit=AuditLogRepository(session),
    )


UserServiceDep = Annotated[UserService, Depends(user_service)]


# ---- KYC adapter (process-singleton) + service ----------------------------
#
# The mock adapter holds in-memory state (the pending registry) so it must be
# a singleton per process. Real adapters (Shufti / Plaid) are stateless HTTP
# clients and the same DI shape works for them too.

_kyc_provider: KycProvider = MockKycAdapter()


def kyc_provider() -> KycProvider:
    return _kyc_provider


def kyc_service(
    session: SessionDep, provider: Annotated[KycProvider, Depends(kyc_provider)]
) -> KycService:
    return KycService(
        kyc=KycRepository(session),
        audit=AuditLogRepository(session),
        provider=provider,
    )


KycProviderDep = Annotated[KycProvider, Depends(kyc_provider)]
KycServiceDep = Annotated[KycService, Depends(kyc_service)]


# ---- Accreditation adapter (process-singleton) + service -----------------

_accreditation_provider: AccreditationProvider = MockAccreditationAdapter()


def accreditation_provider() -> AccreditationProvider:
    return _accreditation_provider


def settings_dep() -> Settings:
    return get_settings()


def accreditation_service(
    session: SessionDep,
    provider: Annotated[AccreditationProvider, Depends(accreditation_provider)],
    settings: Annotated[Settings, Depends(settings_dep)],
) -> AccreditationService:
    return AccreditationService(
        accreditation=AccreditationRepository(session),
        audit=AuditLogRepository(session),
        provider=provider,
        settings=settings,
    )


AccreditationProviderDep = Annotated[AccreditationProvider, Depends(accreditation_provider)]
AccreditationServiceDep = Annotated[AccreditationService, Depends(accreditation_service)]


# ---- token-derived caller (no DB hit) -------------------------------------


@dataclass(frozen=True)
class TokenSubject:
    id: UUID
    email: str
    role: Role


def _unauthenticated() -> DomainError:
    err = DomainError("Authentication required.")
    err.code = ErrorCode.AUTH_TOKEN_INVALID
    err.http_status = 401
    return err


async def token_subject(
    request: Request,
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> TokenSubject:
    if access_token is None:
        raise _unauthenticated()
    payload = decode_token(access_token, expected=TokenType.ACCESS)
    if payload.email is None:
        # Token is well-formed but missing the email claim — treat as invalid.
        raise _unauthenticated()
    request.state.user_id = str(payload.sub)
    return TokenSubject(id=payload.sub, email=payload.email, role=payload.role)


TokenSubjectDep = Annotated[TokenSubject, Depends(token_subject)]


# ---- DB-fresh caller (loads the User row) ---------------------------------


async def current_user(subject: TokenSubjectDep, session: SessionDep) -> User:
    user = await UserRepository(session).get_by_id(subject.id)
    if user is None:
        raise _unauthenticated()
    return user


CurrentUserDep = Annotated[User, Depends(current_user)]


# ---- role gate ------------------------------------------------------------


class RoleRequired:
    """Dependency factory that 403s if the caller's token role isn't allowed.

    Usage:
        admin_only = Depends(RoleRequired(Role.ADMIN))
        @router.get("/admin/foo", dependencies=[admin_only])
    """

    def __init__(self, *roles: Role) -> None:
        if not roles:
            raise ValueError("RoleRequired needs at least one role")
        self._allowed = frozenset(roles)

    async def __call__(self, subject: TokenSubjectDep) -> TokenSubject:
        if subject.role not in self._allowed:
            raise ForbiddenError("Insufficient role.")
        return subject


# ---- refresh cookie -------------------------------------------------------


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
