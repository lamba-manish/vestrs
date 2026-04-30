"""Accreditation vendor adapter — Protocol + mock implementation.

Real vendors (Accred, VerifyInvestor, Parallel Markets) plug in by
implementing ``AccreditationProvider``. The mock simulates the asynchronous
"12-48 hour review" with a configurable delay (default 5s in local), driven
by an in-process registry that ARQ workers poll.
"""

from app.adapters.accreditation.base import (
    AccreditationCheckResult,
    AccreditationProvider,
)
from app.adapters.accreditation.mock import MockAccreditationAdapter

__all__ = [
    "AccreditationCheckResult",
    "AccreditationProvider",
    "MockAccreditationAdapter",
]
