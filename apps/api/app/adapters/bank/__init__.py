"""Bank linking vendor adapter — Protocol + mock implementation.

Real vendors (Plaid, MX, Finicity) plug in by implementing ``BankProvider``.
The mock returns deterministic outcomes via the user's email pattern and
seeds a stable last-4 + balance from the submitted account number.
"""

from app.adapters.bank.base import BankLinkResult, BankProvider
from app.adapters.bank.mock import MockBankAdapter

__all__ = ["BankLinkResult", "BankProvider", "MockBankAdapter"]
