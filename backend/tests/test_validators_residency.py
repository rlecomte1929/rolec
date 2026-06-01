"""Tests for the residency-mismatch validator (C2-02b).

Pure stdlib pytest. Lands independently of runtime.

Run with:
    PYTHONPATH=. python3 -m pytest backend/tests/test_validators_residency.py -v
"""

from __future__ import annotations

import pytest

from backend.relopass.agents.extraction._validators_freshness import Finding
from backend.relopass.agents.extraction._validators_residency import (
    residency_mismatch_finding,
)


class TestResidencyMismatchFinding:
    def test_both_match_returns_none(self) -> None:
        assert (
            residency_mismatch_finding(
                tax_cert_country_iso3="NOR",
                case_employee_country_iso3="NOR",
            )
            is None
        )

    def test_case_insensitive_match_returns_none(self) -> None:
        assert (
            residency_mismatch_finding(
                tax_cert_country_iso3="fra",
                case_employee_country_iso3="FRA",
            )
            is None
        )

    def test_whitespace_tolerant_match_returns_none(self) -> None:
        assert (
            residency_mismatch_finding(
                tax_cert_country_iso3="  FRA  ",
                case_employee_country_iso3="FRA",
            )
            is None
        )

    def test_mismatch_returns_warn(self) -> None:
        f = residency_mismatch_finding(
            tax_cert_country_iso3="FRA",
            case_employee_country_iso3="NOR",
        )
        assert isinstance(f, Finding)
        assert f.severity == "WARN"
        assert f.code == "TAX_CERT_RESIDENCE_MISMATCH"
        assert "FRA" in f.message
        assert "NOR" in f.message
        assert "out of date" in f.message

    def test_reverse_mismatch_returns_warn(self) -> None:
        f = residency_mismatch_finding(
            tax_cert_country_iso3="NOR",
            case_employee_country_iso3="FRA",
        )
        assert isinstance(f, Finding)
        assert f.severity == "WARN"
        assert f.code == "TAX_CERT_RESIDENCE_MISMATCH"

    def test_de_to_no_mismatch(self) -> None:
        f = residency_mismatch_finding(
            tax_cert_country_iso3="DEU",
            case_employee_country_iso3="NOR",
        )
        assert f is not None
        assert "DEU" in f.message and "NOR" in f.message

    @pytest.mark.parametrize(
        "tax,case",
        [
            (None, "NOR"),
            ("NOR", None),
            (None, None),
            ("", "NOR"),
            ("NOR", ""),
        ],
    )
    def test_missing_country_returns_none(self, tax, case) -> None:
        # When either side is missing, we can't determine mismatch.
        # Returning None lets the calling agent decide whether to flag
        # the missing fact separately.
        assert (
            residency_mismatch_finding(
                tax_cert_country_iso3=tax,
                case_employee_country_iso3=case,
            )
            is None
        )

    def test_custom_code_override(self) -> None:
        f = residency_mismatch_finding(
            tax_cert_country_iso3="FRA",
            case_employee_country_iso3="NOR",
            code="FR_NO_RESIDENCE_DRIFT",
        )
        assert f is not None
        assert f.code == "FR_NO_RESIDENCE_DRIFT"

    def test_message_includes_renewal_hint(self) -> None:
        f = residency_mismatch_finding(
            tax_cert_country_iso3="FRA",
            case_employee_country_iso3="NOR",
        )
        assert f is not None
        # The HR-facing hint should point to the right next action.
        assert "updated document" in f.message or "tax authority" in f.message

    def test_finding_is_immutable(self) -> None:
        f = residency_mismatch_finding(
            tax_cert_country_iso3="FRA",
            case_employee_country_iso3="NOR",
        )
        assert f is not None
        with pytest.raises((AttributeError, TypeError)):
            f.severity = "INFO"  # type: ignore[misc]


class TestRealWorldScenarios:
    """End-to-end mirroring the C2-02b fixture personas."""

    def test_marc_bouchard_fr_cert_no_case(self) -> None:
        # FR fr_03_dgfip_residency_mismatch fixture: tax cert FR, case NOR.
        f = residency_mismatch_finding(
            tax_cert_country_iso3="FRA",
            case_employee_country_iso3="NOR",
        )
        assert f is not None
        assert f.code == "TAX_CERT_RESIDENCE_MISMATCH"

    def test_oeztuerk_de_cert_no_case(self) -> None:
        # DE de_03_partial_year fixture: tax cert DE, case NOR.
        f = residency_mismatch_finding(
            tax_cert_country_iso3="DEU",
            case_employee_country_iso3="NOR",
        )
        assert f is not None

    def test_andersen_no_cert_fr_case(self) -> None:
        # NO no_03_residency_mismatch fixture: tax cert NO, case FRA.
        f = residency_mismatch_finding(
            tax_cert_country_iso3="NOR",
            case_employee_country_iso3="FRA",
        )
        assert f is not None
        assert "NOR" in f.message and "FRA" in f.message

    def test_clean_cases_no_mismatch(self) -> None:
        # Hansen (NO→NO), Müller (DE→DE), Dupont (FR→FR) all stay clean.
        assert (
            residency_mismatch_finding(
                tax_cert_country_iso3="NOR",
                case_employee_country_iso3="NOR",
            )
            is None
        )
        assert (
            residency_mismatch_finding(
                tax_cert_country_iso3="DEU",
                case_employee_country_iso3="DEU",
            )
            is None
        )
        assert (
            residency_mismatch_finding(
                tax_cert_country_iso3="FRA",
                case_employee_country_iso3="FRA",
            )
            is None
        )
