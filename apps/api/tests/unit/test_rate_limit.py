"""Pure-logic tests for the rate-limit module.

The integration path (Redis + FastAPI dependency) is exercised in
the integration suite. Here we cover the helpers that can be tested
without hitting Redis: identifier resolution, retry-after math,
constructor validation.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.core.errors import RateLimitedError
from app.core.rate_limit import RateLimit, _client_ip, _identify, global_ip_limit, limit


class _FakeRequest:
    """Minimal Request stand-in for the helpers (only `.headers`,
    `.client`, and `.state` are touched)."""

    def __init__(
        self,
        *,
        forwarded: str | None = None,
        client_host: str | None = None,
        user_id: str | None = None,
    ) -> None:
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}
        self.client = SimpleNamespace(host=client_host) if client_host else None
        self.state = SimpleNamespace(user_id=user_id) if user_id else SimpleNamespace()


def test_client_ip_prefers_x_forwarded_for_first_value() -> None:
    req: Any = _FakeRequest(forwarded="203.0.113.7, 198.51.100.1", client_host="10.0.0.1")
    assert _client_ip(req) == "203.0.113.7"


def test_client_ip_strips_whitespace_in_xff() -> None:
    req: Any = _FakeRequest(forwarded="  203.0.113.9  ")
    assert _client_ip(req) == "203.0.113.9"


def test_client_ip_falls_back_to_request_client_host() -> None:
    req: Any = _FakeRequest(client_host="10.0.0.5")
    assert _client_ip(req) == "10.0.0.5"


def test_client_ip_returns_unknown_when_nothing_available() -> None:
    req: Any = _FakeRequest()
    assert _client_ip(req) == "unknown"


def test_client_ip_returns_unknown_for_empty_xff_value() -> None:
    req: Any = _FakeRequest(forwarded="")
    # Empty string in header → falls through to request.client.host;
    # _FakeRequest leaves client=None, so we land on "unknown".
    assert _client_ip(req) == "unknown"


@pytest.mark.asyncio
async def test_identify_uses_user_id_by_default() -> None:
    req: Any = _FakeRequest(user_id="u-123", client_host="1.2.3.4")
    assert await _identify(req) == "u:u-123"


@pytest.mark.asyncio
async def test_identify_force_ip_ignores_user_id() -> None:
    req: Any = _FakeRequest(user_id="u-123", client_host="1.2.3.4")
    assert await _identify(req, force_ip=True) == "ip:1.2.3.4"


@pytest.mark.asyncio
async def test_identify_falls_back_to_ip_when_no_user() -> None:
    req: Any = _FakeRequest(client_host="1.2.3.4")
    assert await _identify(req) == "ip:1.2.3.4"


# ---------- constructor validation ----------


@pytest.mark.parametrize("times,seconds", [(0, 60), (-1, 60), (10, 0), (10, -5)])
def test_constructor_rejects_non_positive_times_or_seconds(times: int, seconds: int) -> None:
    with pytest.raises(ValueError, match="times and seconds must be positive"):
        RateLimit(times=times, seconds=seconds)


def test_constructor_rejects_unknown_identify_by() -> None:
    with pytest.raises(ValueError, match="identify_by must be 'auto' or 'ip'"):
        RateLimit(times=10, seconds=60, identify_by="email")  # type: ignore[arg-type]


def test_limit_factory_returns_a_rate_limit() -> None:
    rl = limit(times=5, seconds=10, bucket="x")
    assert isinstance(rl, RateLimit)
    assert rl.times == 5
    assert rl.seconds == 10
    assert rl.bucket == "x"
    assert rl.identify_by == "auto"


def test_global_ip_limit_is_100_per_minute_ip_bucketed() -> None:
    assert global_ip_limit.times == 100
    assert global_ip_limit.seconds == 60
    assert global_ip_limit.bucket == "global:ip"
    assert global_ip_limit.identify_by == "ip"


# ---------- _retry_after_from_oldest ----------


def test_retry_after_falls_back_to_full_window_when_oldest_missing() -> None:
    rl = RateLimit(times=10, seconds=60)
    now_ms = 1_000_000_000
    assert rl._retry_after_from_oldest([], now_ms) == 60


def test_retry_after_computes_seconds_until_window_clears() -> None:
    rl = RateLimit(times=10, seconds=60)
    now_ms = 1_000_000_000
    # Oldest entry was 30s ago — should clear in another 30s.
    oldest = [("entry", float(now_ms - 30_000))]
    assert rl._retry_after_from_oldest(oldest, now_ms) == 30


def test_retry_after_rounds_up_partial_seconds() -> None:
    rl = RateLimit(times=10, seconds=60)
    now_ms = 1_000_000_000
    # Oldest entry 59,500ms ago → 500ms remaining → 1s rounded.
    oldest = [("entry", float(now_ms - 59_500))]
    assert rl._retry_after_from_oldest(oldest, now_ms) == 1


def test_retry_after_floors_at_one_second() -> None:
    rl = RateLimit(times=10, seconds=60)
    now_ms = 1_000_000_000
    # Oldest entry exactly at the window boundary — would be 0; we
    # always return ≥1 so clients see a non-zero hint.
    oldest = [("entry", float(now_ms - 60_000))]
    assert rl._retry_after_from_oldest(oldest, now_ms) == 1


def test_retry_after_used_when_constructing_rate_limited_error() -> None:
    err = RateLimitedError(retry_after_seconds=42)
    assert err.retry_after_seconds == 42
    assert err.code.value == "RATE_LIMITED"


def test_rate_limited_error_default_has_no_retry_after() -> None:
    err = RateLimitedError()
    assert err.retry_after_seconds is None
