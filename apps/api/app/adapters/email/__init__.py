"""Email adapter — `Protocol` + the SMTP implementation.

Slice 26 introduces a single transactional email (welcome on signup).
Future flows (KYC outcome, accreditation resolved, investment receipt)
plug in the same way: build the message in a helper, call
``adapter.send(...)`` from an ARQ job. Synchronous-on-the-request
sending is intentionally not supported — email shouldn't slow down
or fail HTTP responses.
"""

from app.adapters.email.base import EmailAdapter, EmailMessage
from app.adapters.email.smtp import NullEmailAdapter, SmtpEmailAdapter

__all__ = ["EmailAdapter", "EmailMessage", "NullEmailAdapter", "SmtpEmailAdapter"]
