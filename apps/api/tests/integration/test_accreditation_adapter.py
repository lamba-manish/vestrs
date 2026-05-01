"""MockAccreditationAdapter contract — integration test (uses real Redis)."""

from __future__ import annotations

import asyncio
import os

import pytest
import uuid6

from app.adapters.accreditation import MockAccreditationAdapter
from app.models.accreditation import AccreditationStatus

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/15")


@pytest.fixture
async def adapter(monkeypatch: pytest.MonkeyPatch) -> MockAccreditationAdapter:
    monkeypatch.setenv("REDIS_URL", REDIS_URL)
    from app.core import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    instance = MockAccreditationAdapter()
    yield instance
    await instance.aclose()


async def test_submit_returns_pending(adapter: MockAccreditationAdapter) -> None:
    out = await adapter.submit_check(
        user_id=uuid6.uuid6(),
        email="alice@example.com",
        full_name="Alice",
        nationality="US",
        domicile="US",
        delay_seconds=60,
        path="income",
        path_passes_sec=True,
        path_failure_reason=None,
        path_data={},
    )
    assert out.status is AccreditationStatus.PENDING
    assert out.provider_reference.startswith("mock-acc-")


async def test_fetch_within_delay_still_pending(
    adapter: MockAccreditationAdapter,
) -> None:
    out = await adapter.submit_check(
        user_id=uuid6.uuid6(),
        email="alice@example.com",
        full_name=None,
        nationality=None,
        domicile=None,
        delay_seconds=60,
        path="income",
        path_passes_sec=True,
        path_failure_reason=None,
        path_data={},
    )
    refetch = await adapter.fetch_status(provider_reference=out.provider_reference)
    assert refetch.status is AccreditationStatus.PENDING


async def test_fetch_after_delay_returns_terminal(
    adapter: MockAccreditationAdapter,
) -> None:
    out = await adapter.submit_check(
        user_id=uuid6.uuid6(),
        email="alice@example.com",
        full_name=None,
        nationality=None,
        domicile=None,
        delay_seconds=1,
        path="income",
        path_passes_sec=True,
        path_failure_reason=None,
        path_data={},
    )
    await asyncio.sleep(1.2)
    refetch = await adapter.fetch_status(provider_reference=out.provider_reference)
    assert refetch.status is AccreditationStatus.SUCCESS


async def test_acc_fail_email_resolves_to_failed(
    adapter: MockAccreditationAdapter,
) -> None:
    out = await adapter.submit_check(
        user_id=uuid6.uuid6(),
        email="bob+acc_fail@example.com",
        full_name=None,
        nationality=None,
        domicile=None,
        delay_seconds=0,
        path="income",
        path_passes_sec=True,
        path_failure_reason=None,
        path_data={},
    )
    refetch = await adapter.fetch_status(provider_reference=out.provider_reference)
    assert refetch.status is AccreditationStatus.FAILED
    assert refetch.failure_reason == "income_documentation_insufficient"


async def test_force_resolve_short_circuits_delay(
    adapter: MockAccreditationAdapter,
) -> None:
    out = await adapter.submit_check(
        user_id=uuid6.uuid6(),
        email="alice@example.com",
        full_name=None,
        nationality=None,
        domicile=None,
        delay_seconds=600,
        path="income",
        path_passes_sec=True,
        path_failure_reason=None,
        path_data={},
    )
    await adapter.force_resolve(out.provider_reference, status=AccreditationStatus.SUCCESS)
    refetch = await adapter.fetch_status(provider_reference=out.provider_reference)
    assert refetch.status is AccreditationStatus.SUCCESS
