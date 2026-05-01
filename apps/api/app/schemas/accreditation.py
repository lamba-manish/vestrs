"""Accreditation API schemas.

Slice 29: the request body is a discriminated union over the three
SEC-recognised paths to accredited-investor status. Each path's
schema enforces the regulatory thresholds at the API boundary so the
service layer can trust the input and the mock adapter can decide
the outcome from validated values.

Reference: https://www.sec.gov/resources-small-businesses/capital-raising-building-blocks/accredited-investors
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# SEC thresholds — re-exported so the adapter and tests share one source of truth.
SEC_INCOME_INDIVIDUAL_USD = Decimal("200000")
SEC_INCOME_JOINT_USD = Decimal("300000")
SEC_NET_WORTH_USD = Decimal("1000000")
SEC_REQUIRED_INCOME_YEARS = 2
SEC_VALID_LICENSES = frozenset({"series_7", "series_65", "series_82"})


class IncomeAccreditation(BaseModel):
    """Income test under SEC Reg D 506(c)(2)(ii)(D)(1).

    The user attests to two consecutive years of qualifying income and a
    reasonable expectation of the same in the current year. Numbers are
    USD; the regulation is dollar-denominated.
    """

    model_config = ConfigDict(extra="forbid")

    path: Literal["income"]
    annual_income_usd: Annotated[Decimal, Field(ge=0, decimal_places=2)]
    joint_with_spouse: bool
    years_at_or_above: Annotated[int, Field(ge=1, le=10)]
    expects_same_current_year: bool


class NetWorthAccreditation(BaseModel):
    """Net-worth test under Reg D 506(c)(2)(ii)(D)(2).

    Net worth includes individual + spouse (or spousal-equivalent) assets,
    EXCLUDING the value of the primary residence. The form forces the
    exclusion attestation so we don't accept ambiguous data.
    """

    model_config = ConfigDict(extra="forbid")

    path: Literal["net_worth"]
    net_worth_usd: Annotated[Decimal, Field(ge=0, decimal_places=2)]
    joint_with_spouse: bool
    excludes_primary_residence: bool


class ProfessionalCertAccreditation(BaseModel):
    """Professional certification under the 2020 amendment to Reg D.

    The SEC named Series 7 / 65 / 82 explicitly. We accept those three
    plus a non-empty license number; the mock adapter doesn't talk to
    FINRA, so the number is the user's attestation.
    """

    model_config = ConfigDict(extra="forbid")

    path: Literal["professional_certification"]
    license_kind: Literal["series_7", "series_65", "series_82"]
    license_number: Annotated[str, Field(min_length=3, max_length=32)]


# Discriminated union — pydantic picks the right model from `path`.
AccreditationSubmitRequest = Annotated[
    IncomeAccreditation | NetWorthAccreditation | ProfessionalCertAccreditation,
    Field(discriminator="path"),
]


class AccreditationCheckPublic(BaseModel):
    id: UUID
    attempt_number: int
    status: str
    path: str | None = None
    provider_name: str
    provider_reference: str | None = None
    failure_reason: str | None = None
    requested_at: datetime
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AccreditationSummary(BaseModel):
    """GET /accreditation aggregate state."""

    status: str
    latest: AccreditationCheckPublic | None = None


def evaluate_path_outcome(
    body: IncomeAccreditation | NetWorthAccreditation | ProfessionalCertAccreditation,
) -> tuple[bool, str | None]:
    """Apply SEC criteria to the user's attestation.

    Returns ``(passes, failure_reason)``. Living next to the schemas (not
    in the adapter) so the validation rules and the constants stay in
    lock-step — change a threshold here and the failure reason auto-syncs.
    """
    if isinstance(body, IncomeAccreditation):
        threshold = SEC_INCOME_JOINT_USD if body.joint_with_spouse else SEC_INCOME_INDIVIDUAL_USD
        if body.annual_income_usd < threshold:
            return False, "income_threshold_not_met"
        if body.years_at_or_above < SEC_REQUIRED_INCOME_YEARS:
            return False, "insufficient_income_history"
        if not body.expects_same_current_year:
            return False, "no_reasonable_expectation_current_year"
        return True, None

    if isinstance(body, NetWorthAccreditation):
        if not body.excludes_primary_residence:
            return False, "primary_residence_not_excluded"
        if body.net_worth_usd < SEC_NET_WORTH_USD:
            return False, "net_worth_threshold_not_met"
        return True, None

    # ProfessionalCertAccreditation — pydantic Literal already restricted
    # license_kind to the three allowed values; no extra check needed.
    return True, None


def serialise_path_data(
    body: IncomeAccreditation | NetWorthAccreditation | ProfessionalCertAccreditation,
) -> dict[str, Any]:
    """JSONB-safe dump of the user's attestation for persistence + audit."""
    return body.model_dump(mode="json")
