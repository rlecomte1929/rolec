"""The invariant: a national of the destination is never served immigration-permission content.

Every case below is a REAL row from production on 2026-08-30, not an invented example. The
violations are the twelve rows the fix re-scoped; the exemptions are the three it deliberately
left alone. Pinning both directions is the point — a guard that only knows what to reject will
happily strip the posting certificate an Irish national genuinely needs.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from check_nationality_scope import is_permission_content, scan, violates  # noqa: E402


def _row(title, scope, country="FRANCE"):
    return {"country_code": country, "title": title,
            "applies_to_nationality_classes_json": scope}


# ── the defect, as it actually appeared in production ────────────────────────────────

VIOLATIONS = [
    # France — these three were SERVING to Denis, a French national returning to France.
    "EU/EEA/Swiss citizen – permanent residence card (after 5 continuous years)",
    "EU/EEA/Swiss citizen – worker right of residence (optional carte de séjour)",
    "EU/EEA/Swiss citizen – student right of residence (optional carte de séjour)",
    "Carte de séjour UE/EEE — Optional Residence Card for EEA Workers",
    "EEA Residence Right if Involuntarily Unemployed",
    "Entry to France — No Visa for EEA Nationals (EU/EEA nationals)",
    # Ireland — same defect, same shape.
    "Ireland EU/EEA Entry Documents",
    "Ireland EU/EEA Free-Mover Entry Rights",
    "Ireland EU/EEA Residence Registration",
    "Ireland EU/EEA Retained Worker Status",
]


@pytest.mark.parametrize("title", VIOLATIONS)
def test_permission_content_scoped_to_own_nationals_is_a_violation(title):
    assert violates(_row(title, '["OWN_NATIONAL", "EU_EEA"]')), \
        f"not flagged: {title}"


@pytest.mark.parametrize("title", VIOLATIONS)
def test_the_same_row_is_fine_once_own_national_is_dropped(title):
    """The fix is re-scoping, not deletion — an actual EEA mover still needs every one."""
    assert not violates(_row(title, '["EU_EEA"]')), \
        f"still flagged after the fix: {title}"


# ── the boundary: content that legitimately keeps OWN_NATIONAL ───────────────────────

EXEMPT = [
    # Posting under Reg. 883/2004 turns on the SENDING state, not nationality. An Irish
    # national posted from Spain is genuinely in scope.
    ("A1 Certificate — Posted Workers from Spain (EU/EEA nationals)", "IRELAND"),
    ("EU/EEA Social Security Coordination in Ireland", "IRELAND"),
    # Establishment steps apply to a returning national too. france.yaml seeds these
    # as [OWN_NATIONAL, EU_EEA] on purpose and its comment warns against "fixing" them.
    ("Ireland Proof of Address for PPSN and Banking", "IRELAND"),
    ("Justificatif de domicile (proof of French address)", "FRANCE"),
    ("Valid passport or national identity card", "FRANCE"),
    ("Signed French employment contract", "FRANCE"),
    # Health affiliation is residence-BASED but is not permission to reside.
    ("Two CPAM affiliation routes exist: worker-based and PUMa residence-based", "FRANCE"),
]


@pytest.mark.parametrize("title,country", EXEMPT)
def test_non_permission_content_may_keep_own_national(title, country):
    assert not violates(_row(title, '["OWN_NATIONAL", "EU_EEA"]', country)), \
        f"over-corrected — this legitimately reaches a returning national: {title}"


# ── scope handling ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("scope", [None, "", "[]", '["EU_EEA"]', '["THIRD_COUNTRY"]'])
def test_a_row_without_own_national_is_never_a_violation(scope):
    assert not violates(_row("Carte de séjour UE/EEE — Optional Residence Card", scope))


def test_a_universal_row_is_not_a_violation():
    """`null` scope means "applies to everyone" — correct for tax, PRSI and USC."""
    assert not violates(_row("Universal Social Charge — Threshold", None, "IRELAND"))


def test_malformed_scope_does_not_crash_or_false_positive():
    assert not violates(_row("Carte de séjour UE/EEE", "not-json"))
    assert not violates(_row("Carte de séjour UE/EEE", '{"a": 1}'))


def test_scan_reports_country_and_title():
    rows = [
        _row("Ireland EU/EEA Residence Registration", '["OWN_NATIONAL"]', "IRELAND"),
        _row("A1 Certificate — Posted Workers from Spain", '["OWN_NATIONAL"]', "IRELAND"),
    ]
    assert scan(rows) == [("IRELAND", "Ireland EU/EEA Residence Registration")]


def test_the_exemption_beats_the_match():
    """'A1 Certificate' mentions no permission concept, but a title could carry both.
    An exemption must win, or the posting certificate gets stripped."""
    assert not is_permission_content(
        "A1 Certificate — Posted Workers and their right of residence"
    )
