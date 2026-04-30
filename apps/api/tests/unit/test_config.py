"""Settings parsing — covers the comma-separated CORS quirk found by the pre-push gate."""

from __future__ import annotations

import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://localhost:3000", ["http://localhost:3000"]),
        ("http://a,http://b", ["http://a", "http://b"]),
        ("  http://a  ,  http://b  ", ["http://a", "http://b"]),
        ("", []),
        ('["http://a","http://b"]', ["http://a", "http://b"]),
    ],
)
def test_cors_allow_origins_accepts_csv_or_json(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: list[str]
) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", raw)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.cors_allow_origins == expected
