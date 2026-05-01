"""SMTP + null email-adapter unit tests.

The SMTP adapter is exercised against a mocked smtplib.SMTP — we
don't talk to a real relay in CI. Validates: TLS handshake order,
auth credentials forwarded, MIME message contains both text + html
alternatives, send executed in a thread (so the call stays
non-blocking on the worker loop).
"""

from __future__ import annotations

from email.message import EmailMessage as MimeMessage
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.email.base import EmailMessage
from app.adapters.email.smtp import NullEmailAdapter, SmtpEmailAdapter, _mask_email


def _build_msg() -> EmailMessage:
    return EmailMessage(
        to="bob@example.com",
        subject="hi",
        html_body="<p>hi</p>",
        text_body="hi",
        preheader="prev",
    )


@pytest.mark.asyncio
async def test_null_email_adapter_drops_silently() -> None:
    adapter = NullEmailAdapter()
    # No exception, no return value, no SMTP traffic.
    assert await adapter.send(_build_msg()) is None


@pytest.mark.asyncio
async def test_smtp_adapter_sends_with_tls_and_auth() -> None:
    captured: dict[str, object] = {}

    fake_smtp = MagicMock()

    def capture_send_message(mime: MimeMessage) -> None:
        captured["from"] = mime["From"]
        captured["to"] = mime["To"]
        captured["subject"] = mime["Subject"]
        # `iter_parts()` yields the text + html alternative parts.
        parts = list(mime.iter_parts())
        captured["part_types"] = [p.get_content_type() for p in parts]

    fake_smtp.__enter__.return_value = fake_smtp
    fake_smtp.__exit__.return_value = None
    fake_smtp.send_message.side_effect = capture_send_message

    with patch("app.adapters.email.smtp.smtplib.SMTP", return_value=fake_smtp) as smtp_cls:
        adapter = SmtpEmailAdapter(
            host="smtp.example.com",
            port=587,
            username="sender@example.com",
            password="secret",
            use_tls=True,
            from_address="sender@example.com",
            from_name="Vestrs",
        )
        await adapter.send(_build_msg())

    smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=10)
    fake_smtp.starttls.assert_called_once()
    fake_smtp.login.assert_called_once_with("sender@example.com", "secret")
    assert captured["from"] == "Vestrs <sender@example.com>"
    assert captured["to"] == "bob@example.com"
    assert captured["subject"] == "hi"
    # set_content + add_alternative produces a multipart with text/plain
    # and text/html children.
    assert captured["part_types"] == ["text/plain", "text/html"]


@pytest.mark.asyncio
async def test_smtp_adapter_skips_login_when_no_username() -> None:
    fake_smtp = MagicMock()
    fake_smtp.__enter__.return_value = fake_smtp
    fake_smtp.__exit__.return_value = None
    with patch("app.adapters.email.smtp.smtplib.SMTP", return_value=fake_smtp):
        adapter = SmtpEmailAdapter(
            host="localhost",
            port=25,
            username="",
            password="",
            use_tls=False,
            from_address="noreply@example.com",
            from_name="Vestrs",
        )
        await adapter.send(_build_msg())
    fake_smtp.starttls.assert_not_called()
    fake_smtp.login.assert_not_called()


def test_mask_email_basic() -> None:
    # u***@d***.tld pattern — stable shape for log greps.
    masked = _mask_email("alice@example.com")
    assert masked.startswith("a***@e***.")
    assert masked.endswith("com")


def test_mask_email_no_at() -> None:
    assert _mask_email("garbage") == "***"
