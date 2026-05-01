"""Email-adapter Protocol + dataclass.

The Protocol is what services depend on. Concrete implementations
live alongside (`smtp.py`, `null.py`-equivalent inside smtp.py for
local-dev / tests). Adding a new transport (SES, Postmark, …) is a
new file implementing `EmailAdapter` — call sites don't change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    html_body: str
    text_body: str
    # Inbox-preview snippet shown in Gmail / Apple Mail before the user
    # opens the message. Keep it under ~120 chars; longer values are
    # truncated by clients.
    preheader: str | None = None


class EmailAdapter(Protocol):
    async def send(self, message: EmailMessage) -> None: ...
