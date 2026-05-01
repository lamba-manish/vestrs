"""Welcome-email worker job + enqueue helper.

We don't bring up a real arq worker here — that lives in the
integration suite. Unit tests cover:

* `_build_email_adapter` returns NullEmailAdapter when SMTP_HOST is
  unset, SmtpEmailAdapter otherwise (so empty-config envs don't fail
  signup).
* `send_welcome_email` calls the adapter with a rendered message and
  reports "sent" / "failed" without raising.
* `enqueue_welcome_email` swallows Redis-unavailable so signup keeps
  working when the queue is down.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.email.base import EmailMessage
from app.adapters.email.smtp import NullEmailAdapter, SmtpEmailAdapter
from app.workers import worker as worker_module


def test_build_email_adapter_returns_null_when_smtp_host_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.workers.worker.get_settings", _settings_factory(smtp_host=""))
    assert isinstance(worker_module._build_email_adapter(), NullEmailAdapter)


def test_build_email_adapter_returns_smtp_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.workers.worker.get_settings",
        _settings_factory(
            smtp_host="smtp.example.com",
            smtp_from_address="noreply@example.com",
        ),
    )
    assert isinstance(worker_module._build_email_adapter(), SmtpEmailAdapter)


def test_build_email_adapter_returns_null_when_from_address_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Both must be set to actually send; missing from address falls back
    # to NullEmailAdapter rather than booting a half-configured sender.
    monkeypatch.setattr(
        "app.workers.worker.get_settings",
        _settings_factory(smtp_host="smtp.example.com", smtp_from_address=""),
    )
    assert isinstance(worker_module._build_email_adapter(), NullEmailAdapter)


@pytest.mark.asyncio
async def test_send_welcome_email_invokes_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_adapter = MagicMock()
    fake_adapter.send = AsyncMock(return_value=None)
    monkeypatch.setattr("app.workers.worker._email_adapter", fake_adapter)
    monkeypatch.setattr(
        "app.workers.worker.get_settings",
        _settings_factory(public_web_url="https://example.com"),
    )

    result = await worker_module.send_welcome_email({}, "alice@example.com")
    assert result == "sent"
    fake_adapter.send.assert_awaited_once()
    sent: EmailMessage = fake_adapter.send.await_args.args[0]
    assert sent.to == "alice@example.com"
    assert "https://example.com/dashboard" in sent.html_body


@pytest.mark.asyncio
async def test_send_welcome_email_swallows_adapter_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_adapter = MagicMock()
    fake_adapter.send = AsyncMock(side_effect=RuntimeError("smtp refused"))
    monkeypatch.setattr("app.workers.worker._email_adapter", fake_adapter)
    monkeypatch.setattr(
        "app.workers.worker.get_settings",
        _settings_factory(public_web_url="https://example.com"),
    )
    # Job returns "failed" rather than raising — arq won't retry forever
    # and the API isn't impacted.
    assert await worker_module.send_welcome_email({}, "alice@example.com") == "failed"


@pytest.mark.asyncio
async def test_enqueue_welcome_email_swallows_redis_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _raise(*_: Any, **__: Any) -> Any:
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.workers.worker.create_pool", _raise)
    # Should return cleanly — signup must never see a ConnectionError.
    await worker_module.enqueue_welcome_email("alice@example.com")


@pytest.mark.asyncio
async def test_enqueue_welcome_email_pushes_job(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_pool = MagicMock()
    fake_pool.enqueue_job = AsyncMock()
    fake_pool.aclose = AsyncMock()

    async def _make_pool(_settings: Any) -> Any:
        return fake_pool

    monkeypatch.setattr("app.workers.worker.create_pool", _make_pool)
    await worker_module.enqueue_welcome_email("alice@example.com")
    fake_pool.enqueue_job.assert_awaited_once()
    args, kwargs = fake_pool.enqueue_job.await_args
    assert args[0] == "send_welcome_email"
    assert args[1] == "alice@example.com"
    assert kwargs.get("_queue_name") == worker_module.WorkerSettings.queue_name


# ---- helpers ---------------------------------------------------------


def _settings_factory(**overrides: Any) -> Any:
    """Return a callable that produces a Settings-shaped object with the
    given attributes. We avoid constructing a real Settings instance
    (which requires .env defaults) by building a small namespace."""

    class _Stub:
        smtp_host: str = ""
        smtp_port: int = 587
        smtp_username: str = ""
        smtp_password: str = ""
        smtp_use_tls: bool = True
        smtp_from_address: str = ""
        smtp_from_name: str = "Vestrs"
        public_web_url: str = "http://localhost:3000"
        redis_url: str = "redis://redis:6379/0"

    for key, value in overrides.items():
        setattr(_Stub, key, value)

    def _factory() -> Any:
        return _Stub()

    return _factory
