"""Current-user / profile endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import CurrentUserDep, RequestCtxDep, UserServiceDep
from app.core.envelope import success_envelope
from app.schemas.users import ProfileUpdateRequest, UserProfile

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    summary="Return the authenticated user's profile (DB-fresh)",
)
async def get_me(request: Request, user: CurrentUserDep) -> dict[str, object]:
    return success_envelope(
        UserProfile.model_validate(user).model_dump(mode="json"),
        request_id=request.state.request_id,
    )


@router.put(
    "/me",
    summary="Set or update the authenticated user's onboarding profile",
)
async def update_me(
    body: ProfileUpdateRequest,
    request: Request,
    user: CurrentUserDep,
    service: UserServiceDep,
    ctx: RequestCtxDep,
) -> dict[str, object]:
    updated = await service.update_profile(
        user=user,
        full_name=body.full_name,
        nationality=body.nationality,
        domicile=body.domicile,
        phone=body.phone,
        ctx=ctx,
    )
    return success_envelope(
        UserProfile.model_validate(updated).model_dump(mode="json"),
        request_id=request.state.request_id,
    )
