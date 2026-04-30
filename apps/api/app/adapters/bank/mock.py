"""Mock bank adapter — deterministic outcomes by email tag.

Email rules (case-insensitive):

- ``you+bank_fail@example.com`` → link rejected (``credentials_invalid``).
- anything else                  → link succeeds.

Mock balance is derived deterministically from the account-number digits so
test fixtures can produce predictable funded accounts. Never seeded with the
plaintext account number — only its last 4 are echoed back.
"""

from __future__ import annotations

import hashlib
import secrets
from decimal import Decimal
from typing import Any

from app.adapters.bank.base import BankLinkResult


def _provider_account_id() -> str:
    return f"mock-bank-{secrets.token_hex(8)}"


def _balance_for(account_number: str) -> Decimal:
    """Stable per-account-number mock balance in [10_000, 1_000_000]."""
    digest = hashlib.sha256(account_number.encode("utf-8")).digest()
    n = int.from_bytes(digest[:6], "big")
    rng = 990_000  # 1_000_000 - 10_000
    return Decimal(10_000 + (n % rng)).quantize(Decimal("0.0001"))


class MockBankAdapter:
    name = "mock"

    async def link_account(
        self,
        *,
        email: str,
        bank_name: str,
        account_holder_name: str,
        account_number: str,
        routing_number: str,
        currency: str,
    ) -> BankLinkResult:
        local = email.split("@", 1)[0].lower()
        last_four = account_number[-4:].rjust(4, "0")

        if "+bank_fail" in local:
            return BankLinkResult(
                success=False,
                provider_account_id="",
                last_four=last_four,
                mock_balance=Decimal("0"),
                failure_reason="credentials_invalid",
                raw={"provider": self.name, "decision": "deny"},
            )

        balance = _balance_for(account_number)
        meta: dict[str, Any] = {
            "provider": self.name,
            "decision": "approve",
            "bank_name": bank_name,
            "currency": currency,
            "holder_present": bool(account_holder_name),
        }
        return BankLinkResult(
            success=True,
            provider_account_id=_provider_account_id(),
            last_four=last_four,
            mock_balance=balance,
            raw=meta,
        )

    async def unlink_account(self, *, provider_account_id: str) -> None:
        # Real vendors get a webhook here. Mock is a no-op.
        return None
