"""User profile service."""

from __future__ import annotations

from app.models.audit_log import AuditAction, AuditStatus
from app.models.user import User
from app.repositories.audit_logs import AuditLogRepository
from app.repositories.users import UserRepository
from app.services.auth import RequestContext


class UserService:
    def __init__(self, users: UserRepository, audit: AuditLogRepository) -> None:
        self.users = users
        self.audit = audit

    async def update_profile(
        self,
        *,
        user: User,
        full_name: str,
        nationality: str,
        domicile: str,
        phone: str,
        ctx: RequestContext,
    ) -> User:
        previous = {
            "full_name_was_set": user.full_name is not None,
            "nationality_was_set": user.nationality is not None,
            "domicile_was_set": user.domicile is not None,
            "phone_was_set": user.phone is not None,
        }
        updated = await self.users.update_profile(
            user=user,
            full_name=full_name,
            nationality=nationality,
            domicile=domicile,
            phone=phone,
        )
        await self.audit.write(
            action=AuditAction.PROFILE_UPDATED,
            status=AuditStatus.SUCCESS,
            user_id=updated.id,
            resource_type="user",
            resource_id=updated.id,
            request_id=ctx.request_id,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
            metadata=previous,
        )
        return updated
