"""
Phase 1: employee-level targeting on the compensation matrix.

Three things need to hold together for the new axis to be safe:
  1. normalize_employee_level maps the canonical slugs + the legacy aliases
     (Band1..4, L1..4, job-title variants).
  2. row_matches_targeting treats empty employee_levels as "applies to all"
     (back-compat) and otherwise filters strictly (employee-facing) or
     permissively (HR preview) exactly like the two existing axes.
  3. compute_targeting_signature includes the new axis in the hash only
     when non-empty, so pre-existing rows keep their old 2-axis or
     "global" signature and the DB UNIQUE constraint stays intact.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.policy_config_matrix_service import (
    PolicyConfigMatrixService,
    compute_targeting_signature,
)
from backend.app.services.policy_config_targeting import (
    EMPLOYEE_LEVELS,
    normalize_employee_level,
    row_matches_targeting,
    validate_optional_query_employee_level,
)


class NormalizeEmployeeLevelTests(unittest.TestCase):
    def test_canonical_slugs_round_trip(self) -> None:
        for slug in EMPLOYEE_LEVELS:
            self.assertEqual(normalize_employee_level(slug), slug)

    def test_legacy_band_labels(self) -> None:
        self.assertEqual(normalize_employee_level("Band1"), "entry")
        self.assertEqual(normalize_employee_level("Band2"), "manager")
        self.assertEqual(normalize_employee_level("Band3"), "director")
        self.assertEqual(normalize_employee_level("Band4"), "vp")

    def test_legacy_l_style(self) -> None:
        self.assertEqual(normalize_employee_level("L2"), "manager")
        self.assertEqual(normalize_employee_level("L-3"), "director")

    def test_c_suite_synonyms(self) -> None:
        for raw in ("ceo", "CFO", "C-suite", "c_suite", "executive"):
            self.assertEqual(normalize_employee_level(raw), "c_suite")

    def test_unknown_returns_none(self) -> None:
        self.assertIsNone(normalize_employee_level("pope"))
        self.assertIsNone(normalize_employee_level(""))
        self.assertIsNone(normalize_employee_level(None))

    def test_query_validator_rejects_unknown(self) -> None:
        with self.assertRaises(ValueError):
            validate_optional_query_employee_level("wizard")
        self.assertEqual(validate_optional_query_employee_level("director"), "director")
        self.assertIsNone(validate_optional_query_employee_level(None))
        self.assertIsNone(validate_optional_query_employee_level(""))


class RowMatchesTargetingEmployeeLevelTests(unittest.TestCase):
    def test_empty_levels_applies_to_all(self) -> None:
        """Back-compat: existing matrix rows (no level set) match every employee."""
        row = {"assignment_types": [], "family_statuses": [], "employee_levels": []}
        for lvl in (None, "entry", "c_suite"):
            self.assertTrue(
                row_matches_targeting(row, None, None, strict_context=True, employee_level=lvl)
            )

    def test_strict_context_missing_level_blocks_narrowed_row(self) -> None:
        """Employee-facing resolution: row narrowed to 'vp' + caller has no level ctx → no match."""
        row = {"assignment_types": [], "family_statuses": [], "employee_levels": ["vp"]}
        self.assertFalse(
            row_matches_targeting(row, None, None, strict_context=True, employee_level=None)
        )

    def test_hr_preview_missing_level_ignores_axis(self) -> None:
        """HR preview (strict_context=False): missing level means 'don't filter on level'."""
        row = {"assignment_types": [], "family_statuses": [], "employee_levels": ["vp"]}
        self.assertTrue(
            row_matches_targeting(row, None, None, strict_context=False, employee_level=None)
        )

    def test_level_match_passes(self) -> None:
        row = {"assignment_types": [], "family_statuses": [], "employee_levels": ["director", "vp"]}
        self.assertTrue(
            row_matches_targeting(row, None, None, strict_context=True, employee_level="director")
        )

    def test_level_mismatch_blocks(self) -> None:
        row = {"assignment_types": [], "family_statuses": [], "employee_levels": ["c_suite"]}
        self.assertFalse(
            row_matches_targeting(row, None, None, strict_context=True, employee_level="entry")
        )

    def test_level_alias_normalized_against_row(self) -> None:
        """Employee profile may carry legacy 'L2'; row stores canonical 'manager'. Still matches."""
        row = {"assignment_types": [], "family_statuses": [], "employee_levels": ["manager"]}
        self.assertTrue(
            row_matches_targeting(row, None, None, strict_context=True, employee_level="L2")
        )

    def test_three_axes_all_must_pass(self) -> None:
        """Row narrowed on all three axes: any single mismatch blocks."""
        row = {
            "assignment_types": ["long_term"],
            "family_statuses": ["dependents"],
            "employee_levels": ["director"],
        }
        # All match.
        self.assertTrue(
            row_matches_targeting(
                row, "long_term", "dependents", strict_context=True, employee_level="director"
            )
        )
        # Level mismatches.
        self.assertFalse(
            row_matches_targeting(
                row, "long_term", "dependents", strict_context=True, employee_level="entry"
            )
        )
        # Family mismatches.
        self.assertFalse(
            row_matches_targeting(
                row, "long_term", "single", strict_context=True, employee_level="director"
            )
        )

    def test_legacy_callers_without_level_kwarg_still_work(self) -> None:
        """Back-compat: callers that haven't been updated to pass the kwarg pass through unchanged."""
        row = {"assignment_types": [], "family_statuses": [], "employee_levels": []}
        self.assertTrue(row_matches_targeting(row, None, None, strict_context=True))


class TargetingSignatureTests(unittest.TestCase):
    def test_empty_levels_preserves_legacy_signature(self) -> None:
        """A row with empty employee_levels must hash the same as before the axis existed."""
        two_axis = compute_targeting_signature(["long_term"], ["dependents"])
        three_axis_empty = compute_targeting_signature(["long_term"], ["dependents"], [])
        self.assertEqual(two_axis, three_axis_empty)

    def test_global_row_unchanged(self) -> None:
        self.assertEqual(compute_targeting_signature([], [], []), "global")
        # Omitted third arg (legacy call) must also return "global".
        self.assertEqual(compute_targeting_signature([], []), "global")

    def test_levels_change_signature(self) -> None:
        """Adding a level must change the hash so UNIQUE doesn't collide two semantically distinct rows."""
        base = compute_targeting_signature(["long_term"], ["dependents"])
        with_levels = compute_targeting_signature(["long_term"], ["dependents"], ["director"])
        self.assertNotEqual(base, with_levels)

    def test_level_order_and_duplicates_do_not_affect_signature(self) -> None:
        a = compute_targeting_signature([], [], ["vp", "director"])
        b = compute_targeting_signature([], [], ["director", "vp", "director"])
        self.assertEqual(a, b)


class _FakeMatrixDb:
    """Minimal duck-typed db for employee_grouped_payload: one published version
    + a fixed benefit list. No jurisdiction overrides (getattr falls back)."""

    def __init__(self, benefits):
        self._benefits = benefits

    def get_latest_published_policy_config_version(self, company_id, config_key):
        return {"id": "ver-1", "version_number": 1, "effective_date": None}

    def list_policy_config_benefits(self, version_id):
        return list(self._benefits)


def _benefit(benefit_key, employee_levels):
    return {
        "id": benefit_key,
        "benefit_key": benefit_key,
        "benefit_label": benefit_key.replace("_", " ").title(),
        "category": None,
        "covered": True,
        "is_active": True,
        "value_type": "currency",
        "amount_value": 3800.0,
        "currency_code": "EUR",
        "unit_frequency": "monthly",
        "assignment_types": ["long_term", "permanent"],
        "family_statuses": ["single", "spouse_partner", "dependents"],
        "employee_levels": employee_levels,
        "display_order": 0,
    }


class EmployeeGroupedPayloadForwardsLevelTests(unittest.TestCase):
    """Regression for the level-forwarding bug: employee_grouped_payload must
    thread employee_level into row_matches_targeting. Before the fix, a fully
    level-gated published config rendered ZERO benefits to every employee
    (the row_matches_targeting unit tests passed; the caller dropped the level).
    """

    def _keys(self, payload):
        keys = set()
        for block in payload.get("categories", []):
            for b in block.get("benefits", []):
                keys.add(b.get("benefit_key"))
        return keys

    def _svc(self):
        return PolicyConfigMatrixService(
            _FakeMatrixDb(
                [
                    _benefit("host_housing_cap", ["director"]),
                    _benefit("manager_perk", ["manager"]),
                    _benefit("global_allowance", []),  # applies to all levels
                ]
            )
        )

    def test_director_sees_director_gated_cap(self):
        payload = self._svc().employee_grouped_payload(
            "co", assignment_type="long_term", family_status="dependents",
            country=None, employee_level="director",
        )
        keys = self._keys(payload)
        self.assertIn("host_housing_cap", keys)   # the bug blanked this
        self.assertIn("global_allowance", keys)
        self.assertNotIn("manager_perk", keys)    # other level correctly excluded

    def test_legacy_band_alias_resolves_to_caps(self):
        payload = self._svc().employee_grouped_payload(
            "co", assignment_type="long_term", family_status="single",
            country=None, employee_level="Band3",  # legacy alias -> director
        )
        self.assertIn("host_housing_cap", self._keys(payload))

    def test_missing_level_drops_level_gated_caps_but_keeps_global(self):
        """Strict employee-facing resolution: no level => level-gated caps are
        dropped (the seniority-gap), but global rows still render."""
        payload = self._svc().employee_grouped_payload(
            "co", assignment_type="long_term", family_status="dependents",
            country=None, employee_level=None,
        )
        keys = self._keys(payload)
        self.assertNotIn("host_housing_cap", keys)
        self.assertNotIn("manager_perk", keys)
        self.assertIn("global_allowance", keys)


if __name__ == "__main__":
    unittest.main()
