"""SEC accreditation path evaluator (slice 29).

The schemas in apps/api/app/schemas/accreditation.py model the three
paths the SEC names (income / net-worth / professional certification)
and `evaluate_path_outcome` decides pass/fail using the regulatory
thresholds. This file pins the threshold logic — change a number in
the schema constants and these tests force a deliberate update.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.schemas.accreditation import (
    SEC_INCOME_INDIVIDUAL_USD,
    SEC_INCOME_JOINT_USD,
    SEC_NET_WORTH_USD,
    IncomeAccreditation,
    NetWorthAccreditation,
    ProfessionalCertAccreditation,
    evaluate_path_outcome,
)

# ---- income -----------------------------------------------------------


def test_income_passes_at_individual_threshold() -> None:
    body = IncomeAccreditation(
        path="income",
        annual_income_usd=SEC_INCOME_INDIVIDUAL_USD,
        joint_with_spouse=False,
        years_at_or_above=2,
        expects_same_current_year=True,
    )
    assert evaluate_path_outcome(body) == (True, None)


def test_income_fails_one_dollar_short_individual() -> None:
    body = IncomeAccreditation(
        path="income",
        annual_income_usd=SEC_INCOME_INDIVIDUAL_USD - 1,
        joint_with_spouse=False,
        years_at_or_above=2,
        expects_same_current_year=True,
    )
    assert evaluate_path_outcome(body) == (False, "income_threshold_not_met")


def test_income_joint_threshold_is_higher() -> None:
    body = IncomeAccreditation(
        path="income",
        annual_income_usd=SEC_INCOME_INDIVIDUAL_USD,  # would pass individual
        joint_with_spouse=True,  # but not joint
        years_at_or_above=2,
        expects_same_current_year=True,
    )
    assert evaluate_path_outcome(body) == (False, "income_threshold_not_met")


def test_income_passes_at_joint_threshold() -> None:
    body = IncomeAccreditation(
        path="income",
        annual_income_usd=SEC_INCOME_JOINT_USD,
        joint_with_spouse=True,
        years_at_or_above=2,
        expects_same_current_year=True,
    )
    assert evaluate_path_outcome(body) == (True, None)


def test_income_requires_two_year_history() -> None:
    body = IncomeAccreditation(
        path="income",
        annual_income_usd=SEC_INCOME_INDIVIDUAL_USD,
        joint_with_spouse=False,
        years_at_or_above=1,
        expects_same_current_year=True,
    )
    assert evaluate_path_outcome(body) == (False, "insufficient_income_history")


def test_income_requires_reasonable_expectation() -> None:
    body = IncomeAccreditation(
        path="income",
        annual_income_usd=SEC_INCOME_INDIVIDUAL_USD,
        joint_with_spouse=False,
        years_at_or_above=2,
        expects_same_current_year=False,
    )
    assert evaluate_path_outcome(body) == (False, "no_reasonable_expectation_current_year")


# ---- net worth --------------------------------------------------------


def test_net_worth_passes_at_threshold() -> None:
    body = NetWorthAccreditation(
        path="net_worth",
        net_worth_usd=SEC_NET_WORTH_USD,
        joint_with_spouse=False,
        excludes_primary_residence=True,
    )
    assert evaluate_path_outcome(body) == (True, None)


def test_net_worth_fails_below_threshold() -> None:
    body = NetWorthAccreditation(
        path="net_worth",
        net_worth_usd=SEC_NET_WORTH_USD - Decimal("0.01"),
        joint_with_spouse=False,
        excludes_primary_residence=True,
    )
    assert evaluate_path_outcome(body) == (False, "net_worth_threshold_not_met")


def test_net_worth_must_exclude_primary_residence() -> None:
    body = NetWorthAccreditation(
        path="net_worth",
        net_worth_usd=SEC_NET_WORTH_USD * 5,  # plenty
        joint_with_spouse=False,
        excludes_primary_residence=False,
    )
    assert evaluate_path_outcome(body) == (False, "primary_residence_not_excluded")


# ---- professional certification ---------------------------------------


@pytest.mark.parametrize("license_kind", ["series_7", "series_65", "series_82"])
def test_professional_cert_passes_for_each_recognised_license(license_kind: str) -> None:
    body = ProfessionalCertAccreditation.model_validate(
        {
            "path": "professional_certification",
            "license_kind": license_kind,
            "license_number": "1234567",
        }
    )
    assert evaluate_path_outcome(body) == (True, None)


def test_professional_cert_rejects_unknown_license_at_schema_layer() -> None:
    # Pydantic Literal validation kicks in before the evaluator sees it,
    # so unknown licenses can't reach evaluate_path_outcome.
    with pytest.raises(ValueError):
        ProfessionalCertAccreditation.model_validate(
            {
                "path": "professional_certification",
                "license_kind": "series_999",
                "license_number": "1234567",
            }
        )
