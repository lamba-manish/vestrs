"""KYC vendor adapter — Protocol + mock implementation.

Real vendors (Shufti Pro, Jumio, Plaid IDV) plug in by implementing
``KycProvider``. The mock provides deterministic outcomes via email-pattern
hints (``+kyc_fail`` / ``+kyc_pending``) so tests + demos stay seedable.
"""

from app.adapters.kyc.base import KycCheckResult, KycProvider
from app.adapters.kyc.mock import MockKycAdapter

__all__ = ["KycCheckResult", "KycProvider", "MockKycAdapter"]
