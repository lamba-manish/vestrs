"""ProfileUpdateRequest validators — country, phone, name."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.users import ProfileUpdateRequest

VALID_PAYLOAD = {
    "full_name": "Ada Lovelace",
    "nationality": "GB",
    "domicile": "US",
    "phone": "+14155551234",
}


def test_valid_payload_round_trips() -> None:
    p = ProfileUpdateRequest(**VALID_PAYLOAD)
    assert p.full_name == "Ada Lovelace"
    assert p.nationality == "GB"
    assert p.domicile == "US"
    assert p.phone == "+14155551234"


def test_lowercase_country_is_normalized_to_upper() -> None:
    p = ProfileUpdateRequest(**{**VALID_PAYLOAD, "nationality": "in", "domicile": "us"})
    assert p.nationality == "IN"
    assert p.domicile == "US"


def test_full_name_is_stripped() -> None:
    p = ProfileUpdateRequest(**{**VALID_PAYLOAD, "full_name": "  Ada Lovelace  "})
    assert p.full_name == "Ada Lovelace"


@pytest.mark.parametrize("bad", ["XX", "ZZ", "ENG", "U"])
def test_invalid_country_rejected(bad: str) -> None:
    with pytest.raises(ValidationError) as exc:
        ProfileUpdateRequest(**{**VALID_PAYLOAD, "nationality": bad})
    assert "nationality" in str(exc.value)


@pytest.mark.parametrize("bad", ["12345", "+1234", "not-a-phone"])
def test_invalid_phone_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        ProfileUpdateRequest(**{**VALID_PAYLOAD, "phone": bad})


def test_phone_normalised_to_e164() -> None:
    # The library reformats already-E.164 inputs; non-E.164 (e.g. national-only)
    # are rejected because we always parse with region=None.
    p = ProfileUpdateRequest(**{**VALID_PAYLOAD, "phone": "+44 20 7946 0958"})
    assert p.phone == "+442079460958"


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        ProfileUpdateRequest(**{**VALID_PAYLOAD, "ssn": "123-45-6789"})


def test_full_name_empty_rejected() -> None:
    with pytest.raises(ValidationError):
        ProfileUpdateRequest(**{**VALID_PAYLOAD, "full_name": "   "})
