"""MockKycAdapter contract tests — every implementation should pass these."""

from __future__ import annotations

import uuid6

from app.adapters.kyc import MockKycAdapter
from app.models.kyc import KycStatus


async def test_default_email_returns_success() -> None:
    adapter = MockKycAdapter()
    out = await adapter.submit_check(
        user_id=uuid6.uuid6(),
        email="alice@example.com",
        full_name="Alice",
        nationality="US",
        domicile="US",
    )
    assert out.status is KycStatus.SUCCESS
    assert out.provider_reference.startswith("mock-kyc-")
    assert out.failure_reason is None


async def test_kyc_fail_tag_returns_failed() -> None:
    adapter = MockKycAdapter()
    out = await adapter.submit_check(
        user_id=uuid6.uuid6(),
        email="bob+kyc_fail@example.com",
        full_name="Bob",
        nationality="US",
        domicile="US",
    )
    assert out.status is KycStatus.FAILED
    assert out.failure_reason == "document_quality_insufficient"


async def test_kyc_pending_tag_returns_pending_and_persists_in_registry() -> None:
    adapter = MockKycAdapter()
    out = await adapter.submit_check(
        user_id=uuid6.uuid6(),
        email="carol+kyc_pending@example.com",
        full_name="Carol",
        nationality="GB",
        domicile="GB",
    )
    assert out.status is KycStatus.PENDING
    refetch = await adapter.fetch_status(provider_reference=out.provider_reference)
    assert refetch.status is KycStatus.PENDING


async def test_resolve_pending_flips_status() -> None:
    adapter = MockKycAdapter()
    out = await adapter.submit_check(
        user_id=uuid6.uuid6(),
        email="dan+kyc_pending@example.com",
        full_name="Dan",
        nationality="GB",
        domicile="GB",
    )
    adapter.resolve_pending(out.provider_reference, status=KycStatus.SUCCESS)
    after = await adapter.fetch_status(provider_reference=out.provider_reference)
    assert after.status is KycStatus.SUCCESS


def test_resolve_pending_rejects_non_terminal() -> None:
    import pytest

    adapter = MockKycAdapter()
    with pytest.raises(ValueError, match="SUCCESS or FAILED"):
        adapter.resolve_pending("anything", status=KycStatus.PENDING)
