"""Auth service: signup, login, refresh, logout.

All paths write the audit log in the same DB transaction as the action.
The route never commits or constructs error responses — the route's
dependency-managed session commits on success and rolls back on raise; the
global handlers shape the error envelope.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.core.errors import AuthError, ConflictError, DomainError, ErrorCode
from app.core.logging import get_logger
from app.core.security import (
    Role,
    TokenType,
    decode_token,
    hash_password,
    hash_refresh_token,
    issue_access_token,
    issue_refresh_token,
    new_jti,
    verify_password,
)
from app.models.audit_log import AuditAction, AuditStatus
from app.models.user import User
from app.repositories.audit_logs import AuditLogRepository
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository

log = get_logger("api.auth")


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    access_expires: datetime
    refresh_token: str
    refresh_expires: datetime


@dataclass(frozen=True)
class AuthResult:
    user: User
    tokens: IssuedTokens


@dataclass(frozen=True)
class _IssuedRefresh:
    tokens: IssuedTokens
    refresh_id: UUID
    family_id: UUID


@dataclass(frozen=True)
class RequestContext:
    request_id: str | None
    ip: str | None
    user_agent: str | None


class AuthService:
    def __init__(
        self,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        audit: AuditLogRepository,
    ) -> None:
        self.users = users
        self.refresh_tokens = refresh_tokens
        self.audit = audit

    # ---- signup -------------------------------------------------------

    async def signup(self, *, email: str, password: str, ctx: RequestContext) -> AuthResult:
        existing = await self.users.get_by_email(email)
        if existing is not None:
            await AuditLogRepository.write_independent(
                action=AuditAction.AUTH_SIGNUP,
                status=AuditStatus.FAILURE,
                request_id=ctx.request_id,
                ip=ctx.ip,
                user_agent=ctx.user_agent,
                metadata={"reason": "email_taken"},
            )
            raise ConflictError("An account with this email already exists.")

        user = await self.users.create(email=email, password_hash=hash_password(password))
        issued = await self._issue_tokens_for(user, family_id=None, ctx=ctx)
        await self.audit.write(
            action=AuditAction.AUTH_SIGNUP,
            status=AuditStatus.SUCCESS,
            user_id=user.id,
            request_id=ctx.request_id,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
        )
        return AuthResult(user=user, tokens=issued.tokens)

    # ---- login --------------------------------------------------------

    async def login(self, *, email: str, password: str, ctx: RequestContext) -> AuthResult:
        user = await self.users.get_by_email(email)
        # Constant-ish work even on miss: hash a dummy password so timing
        # doesn't reveal whether the email exists.
        # NOTE on user enumeration: distinguishing "email not found" from
        # "wrong password" lets an attacker probe registration state. We do
        # it because the product owner asked for specific UX. Recommend
        # reverting to a single AUTH_INVALID_CREDENTIALS code before going
        # live; tracked in CLAUDE.md sec.8.
        if user is None:
            verify_password(password, _DUMMY_HASH)  # constant-ish work
            await AuditLogRepository.write_independent(
                action=AuditAction.AUTH_LOGIN_FAILED,
                status=AuditStatus.FAILURE,
                request_id=ctx.request_id,
                ip=ctx.ip,
                user_agent=ctx.user_agent,
                metadata={"reason": "user_not_found"},
            )
            err = DomainError("Account with this email does not exist.")
            err.code = ErrorCode.AUTH_EMAIL_NOT_FOUND
            err.http_status = 401
            raise err

        if not verify_password(password, user.password_hash):
            await AuditLogRepository.write_independent(
                action=AuditAction.AUTH_LOGIN_FAILED,
                status=AuditStatus.FAILURE,
                user_id=user.id,
                request_id=ctx.request_id,
                ip=ctx.ip,
                user_agent=ctx.user_agent,
                metadata={"reason": "bad_password"},
            )
            err = DomainError("Password is incorrect.")
            err.code = ErrorCode.AUTH_PASSWORD_INCORRECT
            err.http_status = 401
            raise err

        issued = await self._issue_tokens_for(user, family_id=None, ctx=ctx)
        await self.audit.write(
            action=AuditAction.AUTH_LOGIN,
            status=AuditStatus.SUCCESS,
            user_id=user.id,
            request_id=ctx.request_id,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
        )
        return AuthResult(user=user, tokens=issued.tokens)

    # ---- refresh ------------------------------------------------------

    async def refresh(self, *, refresh_token: str, ctx: RequestContext) -> AuthResult:
        payload = decode_token(refresh_token, expected=TokenType.REFRESH)
        stored = await self.refresh_tokens.get_by_id(payload.jti)

        # Reuse detection: the jti decoded fine but the stored row is missing
        # or already rotated/revoked. Whoever holds an outdated refresh token
        # is presumed compromised — revoke the entire family. The revoke +
        # audit must persist even though we will raise; route the work to a
        # fresh session that commits independently of the request session.
        if stored is None or not stored.is_active:
            family_id = stored.family_id if stored is not None else payload.family_id
            await _record_reuse_and_revoke(
                family_id=family_id,
                user_id=payload.sub,
                ctx=ctx,
                metadata={"jti": str(payload.jti)},
            )
            raise _refresh_required("This session has been revoked. Please sign in again.")

        if stored.token_hash != hash_refresh_token(refresh_token):
            # Token jti matched but hash didn't — strong tamper signal.
            await _record_reuse_and_revoke(
                family_id=stored.family_id,
                user_id=stored.user_id,
                ctx=ctx,
                metadata={"reason": "hash_mismatch"},
            )
            raise _refresh_required("Session integrity check failed.")

        user = await self.users.get_by_id(stored.user_id)
        if user is None:
            raise AuthError("User no longer exists.")

        # Issue the replacement (same family) and mark the old one replaced.
        issued = await self._issue_tokens_for(user, family_id=stored.family_id, ctx=ctx)
        await self.refresh_tokens.mark_replaced(
            token_id=stored.id, replacement_id=issued.refresh_id, now=_now()
        )

        await self.audit.write(
            action=AuditAction.AUTH_REFRESH,
            status=AuditStatus.SUCCESS,
            user_id=user.id,
            request_id=ctx.request_id,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
        )
        return AuthResult(user=user, tokens=issued.tokens)

    # ---- logout -------------------------------------------------------

    async def logout(self, *, refresh_token: str | None, ctx: RequestContext) -> None:
        if refresh_token is None:
            return  # nothing to revoke; cookies cleared by the route
        try:
            payload = decode_token(refresh_token, expected=TokenType.REFRESH)
        except DomainError:
            return  # already invalid — clearing cookies is enough

        stored = await self.refresh_tokens.get_by_id(payload.jti)
        if stored is not None and stored.is_active:
            await self.refresh_tokens.revoke(token_id=stored.id, now=_now())
            await self.audit.write(
                action=AuditAction.AUTH_LOGOUT,
                status=AuditStatus.SUCCESS,
                user_id=stored.user_id,
                request_id=ctx.request_id,
                ip=ctx.ip,
                user_agent=ctx.user_agent,
            )

    # ---- helpers ------------------------------------------------------

    async def _issue_tokens_for(
        self, user: User, *, family_id: UUID | None, ctx: RequestContext
    ) -> _IssuedRefresh:
        token_id = new_jti()
        family = family_id if family_id is not None else new_jti()
        role = Role.ADMIN if user.is_admin else Role.USER

        refresh_jwt, refresh_exp = issue_refresh_token(user.id, token_id, family)
        access_jwt, access_exp = issue_access_token(user.id, new_jti(), email=user.email, role=role)

        await self.refresh_tokens.create(
            token_id=token_id,
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_jwt),
            family_id=family,
            expires_at=refresh_exp,
            user_agent=ctx.user_agent,
            ip=ctx.ip,
        )
        return _IssuedRefresh(
            tokens=IssuedTokens(
                access_token=access_jwt,
                access_expires=access_exp,
                refresh_token=refresh_jwt,
                refresh_expires=refresh_exp,
            ),
            refresh_id=token_id,
            family_id=family,
        )


# A precomputed argon2id hash of an arbitrary string, used for constant-ish
# work on login miss to avoid timing-based user enumeration.
_DUMMY_HASH = hash_password("__not_a_real_password__sentinel__")


def _now() -> datetime:
    return datetime.now(UTC)


def _refresh_required(message: str) -> DomainError:
    err = DomainError(message)
    err.code = ErrorCode.AUTH_REFRESH_REQUIRED
    err.http_status = 401
    return err


async def _record_reuse_and_revoke(
    *,
    family_id: UUID | None,
    user_id: UUID | None,
    ctx: RequestContext,
    metadata: dict[str, object],
) -> None:
    """Revoke a refresh-token family AND write the failure audit, both in a
    fresh session that commits immediately. Caller raises after."""
    from sqlalchemy import update

    from app.db.session import get_session_factory
    from app.models.refresh_token import RefreshToken

    factory = get_session_factory()
    async with factory() as session:
        if family_id is not None:
            now = _now()
            result = await session.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.family_id == family_id,
                    RefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=now, updated_at=now)
            )
            log.warning(
                "refresh_reuse_detected",
                family_id=str(family_id),
                revoked_count=int(getattr(result, "rowcount", 0) or 0),
            )
        repo = AuditLogRepository(session)
        await repo.write(
            action=AuditAction.AUTH_REFRESH_REUSE_DETECTED,
            status=AuditStatus.FAILURE,
            user_id=user_id,
            request_id=ctx.request_id,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
            metadata=metadata,
        )
        await session.commit()
