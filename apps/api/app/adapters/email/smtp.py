"""SMTP transport for transactional email.

Uses stdlib smtplib, executed in a thread pool because smtplib is
sync-only. We deliberately avoid pulling in aiosmtplib here — one
welcome email per signup doesn't justify the extra dependency, and
the worker already runs each job on its own asyncio task so the
thread-pool bounce is invisible.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage as MimeMessage

from app.adapters.email.base import EmailMessage
from app.core.logging import get_logger

log = get_logger("email.smtp")


class SmtpEmailAdapter:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool,
        from_address: str,
        from_name: str,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._from_address = from_address
        self._from_name = from_name

    async def send(self, message: EmailMessage) -> None:
        # smtplib is sync — bounce through asyncio.to_thread so the
        # worker's event loop stays unblocked while the SMTP handshake
        # completes (~1 s on Gmail).
        await asyncio.to_thread(self._send_sync, message)

    def _send_sync(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["Subject"] = message.subject
        mime["From"] = f"{self._from_name} <{self._from_address}>"
        mime["To"] = message.to
        # `set_content` builds the text/plain alternative; `add_alternative`
        # then attaches the HTML body so clients pick whichever they
        # prefer. Order matters: set_content first.
        mime.set_content(message.text_body)
        mime.add_alternative(message.html_body, subtype="html")

        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            smtp.ehlo()
            if self._use_tls:
                smtp.starttls()
                smtp.ehlo()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(mime)
        log.info("email_sent", to=_mask_email(message.to), subject=message.subject)


class NullEmailAdapter:
    """Drops messages on the floor. Used in local dev / tests where
    SMTP_HOST is unset, so the signup flow doesn't fail just because
    no relay is configured."""

    async def send(self, message: EmailMessage) -> None:
        log.info(
            "email_skipped_no_smtp_configured",
            to=_mask_email(message.to),
            subject=message.subject,
        )


def _mask_email(email: str) -> str:
    # u***@d***.com — same masking convention used elsewhere in the
    # codebase. Keeps logs PII-light.
    user, _, domain = email.partition("@")
    if not domain:
        return "***"
    domain_head = domain.split(".")[0]
    return f"{user[:1]}***@{domain_head[:1]}***.{domain.split('.', 1)[1] if '.' in domain else ''}"
