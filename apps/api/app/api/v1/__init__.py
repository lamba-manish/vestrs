"""V1 API routers."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.accreditation import router as accreditation_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.bank import router as bank_router
from app.api.v1.investments import router as investments_router
from app.api.v1.kyc import router as kyc_router
from app.api.v1.users import router as users_router
from app.core.rate_limit import global_ip_limit

# Global per-IP cap (100 req/min) applied to every endpoint under
# /api/v1. Per-route buckets (auth/login, kyc, invest, etc.) stack
# on top for endpoints that need tighter abuse defenses.
api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(global_ip_limit)])
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(kyc_router)
api_router.include_router(accreditation_router)
api_router.include_router(bank_router)
api_router.include_router(investments_router)
api_router.include_router(audit_router)
