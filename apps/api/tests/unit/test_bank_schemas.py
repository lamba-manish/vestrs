"""BankLinkRequest validators."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.bank import BankLinkRequest

VALID = {
    "bank_name": "Chase",
    "account_holder_name": "Ada Lovelace",
    "account_type": "checking",
    "account_number": "000123456789",
    "routing_number": "021000021",
    "currency": "USD",
}


def test_valid_payload_round_trips() -> None:
    p = BankLinkRequest(**VALID)
    assert p.bank_name == "Chase"
    assert p.currency == "USD"
    assert p.account_number.get_secret_value() == "000123456789"


def test_currency_is_normalised_to_upper() -> None:
    p = BankLinkRequest(**{**VALID, "currency": "usd"})
    assert p.currency == "USD"


@pytest.mark.parametrize("bad", ["XX", "USDD", "ZZZ", "12"])
def test_invalid_currency_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        BankLinkRequest(**{**VALID, "currency": bad})


@pytest.mark.parametrize(
    "bad",
    ["12-345-6789", "abc123", "1 2 3 4 5 6 7", ""],
)
def test_account_number_must_be_digits(bad: str) -> None:
    with pytest.raises(ValidationError):
        BankLinkRequest(**{**VALID, "account_number": bad})


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        BankLinkRequest(**{**VALID, "ssn": "123-45-6789"})


def test_invalid_account_type_rejected() -> None:
    with pytest.raises(ValidationError):
        BankLinkRequest(**{**VALID, "account_type": "crypto"})
