"""Bank provider Protocol — what vendors implement."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True)
class BankLinkResult:
    success: bool
    provider_account_id: str
    last_four: str
    mock_balance: Decimal
    failure_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class BankProvider(Protocol):
    name: str

    async def link_account(
        self,
        *,
        email: str,
        bank_name: str,
        account_holder_name: str,
        account_number: str,  # plaintext input — only ever lives inside this call
        routing_number: str,
        currency: str,
    ) -> BankLinkResult:
        """Validate + register the account with the vendor. The plaintext
        account/routing numbers must never be persisted by the caller."""
        ...

    async def unlink_account(self, *, provider_account_id: str) -> None:
        """Tell the vendor we're done with this link. Idempotent."""
        ...
