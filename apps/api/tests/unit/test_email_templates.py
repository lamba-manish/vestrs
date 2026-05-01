"""Welcome-email template renderer tests.

Coverage isn't doing anything fancy — it pins the wire shape so an
accidental string-mangling regression (broken {{tags}}, missing
preheader, lost dashboard URL) shows up in CI rather than in a
reviewer's inbox.
"""

from __future__ import annotations

from app.adapters.email.templates import render_welcome_email


def test_render_welcome_email_substitutes_dashboard_url() -> None:
    msg = render_welcome_email(
        recipient_email="alice@example.com",
        dashboard_url="https://vestrs.example.com/dashboard",
    )

    assert msg.to == "alice@example.com"
    assert "Welcome to Vestrs" in msg.subject
    # URL appears in both bodies, exactly once unescaped (text) and once
    # in the href attribute (html).
    assert "https://vestrs.example.com/dashboard" in msg.text_body
    assert 'href="https://vestrs.example.com/dashboard"' in msg.html_body
    # No template tokens leaked through.
    assert "{{" not in msg.html_body
    assert "{{" not in msg.text_body


def test_welcome_email_html_has_outlook_safe_structure() -> None:
    msg = render_welcome_email(
        recipient_email="alice@example.com",
        dashboard_url="https://example.com/dashboard",
    )
    # Table-based layout (essential for Outlook) and explicit colours
    # (so dark-mode auto-invert can't break contrast).
    assert "<table" in msg.html_body
    assert 'bgcolor="#FFFFFF"' in msg.html_body
    assert "color:#1A1A1A" in msg.html_body
    # Pre-header text present and hidden.
    assert "Your private-banking onboarding flow is ready" in msg.html_body
    assert "display:none" in msg.html_body


def test_welcome_email_text_body_has_automated_disclaimer() -> None:
    msg = render_welcome_email(
        recipient_email="alice@example.com",
        dashboard_url="https://example.com/dashboard",
    )
    assert "automated email" in msg.text_body.lower()
    assert "automated email" in msg.html_body.lower()


def test_welcome_email_html_url_is_attribute_escaped() -> None:
    # The URL is escaped before substitution — verify a URL with
    # ampersands renders safely as an attribute.
    msg = render_welcome_email(
        recipient_email="alice@example.com",
        dashboard_url="https://example.com/dashboard?ref=signup&lang=en",
    )
    assert "ref=signup&amp;lang=en" in msg.html_body
    # Plain text doesn't need escaping.
    assert "ref=signup&lang=en" in msg.text_body
