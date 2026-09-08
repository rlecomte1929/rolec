"""Tests for the shared TAX_CERT runtime-findings wiring (C2-02b).

CI-green: pure stdlib, no LLM, no DB, no PDF. Validates that the three
runtime cross-checks (freshness / tax-id format / residence mismatch) are
correctly assembled from a parsed LLM payload by the helper that all three
tax_cert agents call.

Run with:
    PYTHONPATH=. python3 -m pytest backend/tests/test_tax_cert_findings.py -v
"""

from __future__ import annotations

from datetime import date

import pytest

from backend.relopass.agents.extraction._tax_cert_findings import (
    TAX_CERT_FRESHNESS_CODE,
    all_findings,
    issue_date_from_year,
    llm_findings,
    runtime_findings,
)

REF = date(2026, 5, 29)

# Mod-11-valid synthetic FNRs (see fixtures/tax_certs/README.md).
FNR_VALID = "14058510131"
FNR_INVALID = "14058510132"  # last digit flipped


# ─────────────────────────────────────────────────────────────────────────────
# issue_date_from_year
# ─────────────────────────────────────────────────────────────────────────────


class TestIssueDateFromYear:
    def test_derives_year_end(self) -> None:
        assert issue_date_from_year(2024) == date(2024, 12, 31)

    def test_accepts_numeric_string(self) -> None:
        assert issue_date_from_year("2024") == date(2024, 12, 31)

    @pytest.mark.parametrize("bad", [None, "", "abcd", 1800, 3000, []])
    def test_rejects_implausible(self, bad) -> None:
        assert issue_date_from_year(bad) is None


# ─────────────────────────────────────────────────────────────────────────────
# Freshness, routed through runtime_findings
# ─────────────────────────────────────────────────────────────────────────────


class TestFreshnessRouting:
    def test_old_cert_is_stale(self) -> None:
        payload = {"issue_year": 2023, "residence_country_iso3": "FRA"}
        codes = [f.code for f in runtime_findings(
            country="FRA", payload=payload,
            case_employee_country_iso3=None, reference_date=REF,
        )]
        assert TAX_CERT_FRESHNESS_CODE in codes

    def test_recent_cert_not_stale(self) -> None:
        # issue_year 2026 → 2026-12-31, after the reference date → never stale.
        payload = {"issue_year": 2026, "residence_country_iso3": "FRA"}
        codes = [f.code for f in runtime_findings(
            country="FRA", payload=payload,
            case_employee_country_iso3=None, reference_date=REF,
        )]
        assert TAX_CERT_FRESHNESS_CODE not in codes

    def test_missing_issue_year_skips_freshness(self) -> None:
        payload = {"residence_country_iso3": "FRA"}
        codes = [f.code for f in runtime_findings(
            country="FRA", payload=payload,
            case_employee_country_iso3=None, reference_date=REF,
        )]
        assert TAX_CERT_FRESHNESS_CODE not in codes


# ─────────────────────────────────────────────────────────────────────────────
# Tax-id format, routed through runtime_findings
# ─────────────────────────────────────────────────────────────────────────────


class TestTaxIdRouting:
    def test_no_valid_fnr_no_finding(self) -> None:
        payload = {"issue_year": 2026, "tax_id": FNR_VALID, "residence_country_iso3": "NOR"}
        codes = [f.code for f in runtime_findings(
            country="NOR", payload=payload,
            case_employee_country_iso3="NOR", reference_date=REF,
        )]
        assert "TAX_ID_FORMAT_INVALID_NO" not in codes

    def test_no_invalid_fnr_fires(self) -> None:
        payload = {"issue_year": 2026, "tax_id": FNR_INVALID, "residence_country_iso3": "NOR"}
        codes = [f.code for f in runtime_findings(
            country="NOR", payload=payload,
            case_employee_country_iso3="NOR", reference_date=REF,
        )]
        assert "TAX_ID_FORMAT_INVALID_NO" in codes

    def test_fr_short_spi_fires(self) -> None:
        payload = {"issue_year": 2026, "tax_id": "123456789012", "residence_country_iso3": "FRA"}
        codes = [f.code for f in runtime_findings(
            country="FRA", payload=payload,
            case_employee_country_iso3="FRA", reference_date=REF,
        )]
        assert "TAX_ID_FORMAT_INVALID_FR" in codes

    def test_missing_tax_id_skips(self) -> None:
        payload = {"issue_year": 2026, "residence_country_iso3": "DEU"}
        codes = [f.code for f in runtime_findings(
            country="DEU", payload=payload,
            case_employee_country_iso3="DEU", reference_date=REF,
        )]
        assert not any(c.startswith("TAX_ID_FORMAT_INVALID") for c in codes)


# ─────────────────────────────────────────────────────────────────────────────
# Residency mismatch, routed through runtime_findings
# ─────────────────────────────────────────────────────────────────────────────


class TestResidencyRouting:
    def test_mismatch_fires(self) -> None:
        payload = {"issue_year": 2026, "residence_country_iso3": "FRA"}
        codes = [f.code for f in runtime_findings(
            country="FRA", payload=payload,
            case_employee_country_iso3="NOR", reference_date=REF,
        )]
        assert "TAX_CERT_RESIDENCE_MISMATCH" in codes

    def test_match_no_finding(self) -> None:
        payload = {"issue_year": 2026, "residence_country_iso3": "FRA"}
        codes = [f.code for f in runtime_findings(
            country="FRA", payload=payload,
            case_employee_country_iso3="FRA", reference_date=REF,
        )]
        assert "TAX_CERT_RESIDENCE_MISMATCH" not in codes

    def test_no_case_country_skips(self) -> None:
        payload = {"issue_year": 2026, "residence_country_iso3": "FRA"}
        codes = [f.code for f in runtime_findings(
            country="FRA", payload=payload,
            case_employee_country_iso3=None, reference_date=REF,
        )]
        assert "TAX_CERT_RESIDENCE_MISMATCH" not in codes


# ─────────────────────────────────────────────────────────────────────────────
# llm_findings mapping
# ─────────────────────────────────────────────────────────────────────────────


class TestLlmFindings:
    def test_maps_text_verbatim_to_message(self) -> None:
        payload = {"findings": [
            {"severity": "INFO", "code": "JOINT_FILING_DETECTED",
             "text_verbatim": "Mariés - imposition commune", "bbox": [1, 2, 3, 4]},
        ]}
        fs = llm_findings(payload)
        assert len(fs) == 1
        assert fs[0].severity == "INFO"
        assert fs[0].code == "JOINT_FILING_DETECTED"
        assert fs[0].message == "Mariés - imposition commune"
        assert fs[0].bbox == (1, 2, 3, 4)

    def test_skips_malformed_entries(self) -> None:
        payload = {"findings": [
            {"severity": "BOGUS", "code": "X"},      # bad severity
            {"severity": "WARN"},                      # missing code
            "not-a-dict",
            {"severity": "WARN", "code": "OK_ONE"},   # valid, no text → code is message
        ]}
        fs = llm_findings(payload)
        assert [f.code for f in fs] == ["OK_ONE"]
        assert fs[0].message == "OK_ONE"

    def test_no_findings_key(self) -> None:
        assert llm_findings({}) == ()


# ─────────────────────────────────────────────────────────────────────────────
# all_findings composition
# ─────────────────────────────────────────────────────────────────────────────


class TestAllFindings:
    def test_llm_findings_precede_runtime(self) -> None:
        payload = {
            "issue_year": 2023,  # stale
            "tax_id": "123456789012",  # invalid FR SPI
            "residence_country_iso3": "FRA",
            "findings": [{"severity": "INFO", "code": "JOINT_FILING_DETECTED"}],
        }
        fs = all_findings(
            country="FRA", payload=payload,
            case_employee_country_iso3="NOR", reference_date=REF,
        )
        codes = [f.code for f in fs]
        assert codes[0] == "JOINT_FILING_DETECTED"  # LLM finding first
        assert TAX_CERT_FRESHNESS_CODE in codes
        assert "TAX_ID_FORMAT_INVALID_FR" in codes
        assert "TAX_CERT_RESIDENCE_MISMATCH" in codes

    def test_clean_cert_only_llm_findings(self) -> None:
        payload = {
            "issue_year": 2026,
            "tax_id": "1234567890123",  # valid 13-digit SPI
            "residence_country_iso3": "FRA",
            "findings": [],
        }
        fs = all_findings(
            country="FRA", payload=payload,
            case_employee_country_iso3="FRA", reference_date=REF,
        )
        assert fs == ()
