"""MockBankAdapter contract tests."""

from __future__ import annotations

from decimal import Decimal

from app.adapters.bank import MockBankAdapter


async def test_clean_email_succeeds_with_masked_last_four() -> None:
    adapter = MockBankAdapter()
    out = await adapter.link_account(
        email="alice@example.com",
        bank_name="Chase",
        account_holder_name="Alice",
        account_number="000123456789",
        routing_number="021000021",
        currency="USD",
    )
    assert out.success is True
    assert out.last_four == "6789"
    assert out.provider_account_id.startswith("mock-bank-")
    assert out.failure_reason is None
    assert out.mock_balance >= Decimal("10000")
    assert out.mock_balance < Decimal("1000000")


async def test_bank_fail_email_returns_failure() -> None:
    adapter = MockBankAdapter()
    out = await adapter.link_account(
        email="bob+bank_fail@example.com",
        bank_name="Chase",
        account_holder_name="Bob",
        account_number="123456789",
        routing_number="021000021",
        currency="USD",
    )
    assert out.success is False
    assert out.failure_reason == "credentials_invalid"
    assert out.mock_balance == Decimal("0")


async def test_balance_is_deterministic_for_same_account_number() -> None:
    adapter = MockBankAdapter()
    a = await adapter.link_account(
        email="a@example.com",
        bank_name="b",
        account_holder_name="h",
        account_number="555111222333",
        routing_number="021000021",
        currency="USD",
    )
    b = await adapter.link_account(
        email="c@example.com",
        bank_name="b",
        account_holder_name="h",
        account_number="555111222333",
        routing_number="021000021",
        currency="USD",
    )
    assert a.mock_balance == b.mock_balance


async def test_unlink_is_a_noop_for_mock() -> None:
    adapter = MockBankAdapter()
    # Should not raise.
    await adapter.unlink_account(provider_account_id="mock-bank-anything")
