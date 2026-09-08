"""
Unit tests for backend/services/policy_section_c_resolver.py.

Pure-function tests — no DB. The resolver is the contract that PR 2 wires
into the API. If it's wrong here, every downstream test will be wrong.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.policy_section_c_resolver import (  # noqa: E402
    _coerce_countries,
    resolve_effective_benefit,
    resolve_many,
)


def _base(**kwargs) -> dict:
    """Helper: minimal viable base benefit row."""
    row = {
        "id": "base-1",
        "benefit_key": "shipment",
        "amount_value": 5000,
        "currency_code": "USD",
        "cap_rule_json": {"tiers": [{"max": 5000}]},
        "reimbursement_md": "Base reimbursement.",
        "repayment_md": None,
    }
    row.update(kwargs)
    return row


def _override(**kwargs) -> dict:
    """Helper: minimal override row, defaulting to wildcard axes."""
    row = {
        "id": "ov-x",
        "benefit_row_id": "base-1",
        "jurisdiction_countries": ["SG"],
        "employee_level": None,
        "assignment_type": None,
        "amount_value": None,
        "currency_code": None,
        "cap_rule_json": None,
        "reimbursement_md": None,
        "repayment_md": None,
        "display_order": 0,
        "updated_at": "2026-04-27T00:00:00Z",
    }
    row.update(kwargs)
    return row


# --- _coerce_countries -------------------------------------------------------


class CoerceCountriesTests(unittest.TestCase):
    def test_python_list(self) -> None:
        self.assertEqual(_coerce_countries(["sg", "MY"]), ["SG", "MY"])

    def test_json_encoded_list(self) -> None:
        self.assertEqual(_coerce_countries('["sg","MY"]'), ["SG", "MY"])

    def test_postgres_array_literal(self) -> None:
        self.assertEqual(_coerce_countries("{SG,MY}"), ["SG", "MY"])

    def test_single_bare(self) -> None:
        self.assertEqual(_coerce_countries("sg"), ["SG"])

    def test_none_returns_empty(self) -> None:
        self.assertEqual(_coerce_countries(None), [])

    def test_garbage_returns_empty(self) -> None:
        self.assertEqual(_coerce_countries("[not json"), [])
        self.assertEqual(_coerce_countries(123), [])

    def test_strips_whitespace_and_blanks(self) -> None:
        self.assertEqual(_coerce_countries(["  sg ", "", "MY"]), ["SG", "MY"])


# --- resolve_effective_benefit -----------------------------------------------


class ResolveEffectiveBenefitTests(unittest.TestCase):
    def test_no_overrides_returns_base(self) -> None:
        base = _base()
        eff, ov_id = resolve_effective_benefit(base, [], {"country": "SG"})
        self.assertEqual(eff["amount_value"], 5000)
        self.assertEqual(eff["currency_code"], "USD")
        self.assertFalse(eff["override_applied"])
        self.assertIsNone(ov_id)

    def test_no_country_skips_evaluation(self) -> None:
        base = _base()
        ov = _override(amount_value=8000, currency_code="SGD")
        eff, ov_id = resolve_effective_benefit(base, [ov], {"country": ""})
        self.assertEqual(eff["amount_value"], 5000)
        self.assertFalse(eff["override_applied"])
        self.assertIsNone(ov_id)

    def test_jurisdiction_only_match(self) -> None:
        base = _base()
        ov = _override(
            id="ov-sg",
            jurisdiction_countries=["SG"],
            amount_value=8000,
            currency_code="SGD",
        )
        eff, ov_id = resolve_effective_benefit(
            base, [ov], {"country": "SG", "employee_level": None}
        )
        self.assertEqual(eff["amount_value"], 8000)
        self.assertEqual(eff["currency_code"], "SGD")
        self.assertTrue(eff["override_applied"])
        self.assertEqual(ov_id, "ov-sg")

    def test_jurisdiction_plus_level_beats_jurisdiction_only(self) -> None:
        base = _base()
        ov_country_only = _override(
            id="ov-sg-any",
            jurisdiction_countries=["SG"],
            amount_value=7000,
            currency_code="SGD",
        )
        ov_country_level = _override(
            id="ov-sg-mgr",
            jurisdiction_countries=["SG"],
            employee_level="manager",
            amount_value=9500,
            currency_code="SGD",
        )
        eff, ov_id = resolve_effective_benefit(
            base,
            [ov_country_only, ov_country_level],
            {"country": "SG", "employee_level": "manager"},
        )
        self.assertEqual(ov_id, "ov-sg-mgr")
        self.assertEqual(eff["amount_value"], 9500)

    def test_jurisdiction_level_assignment_beats_jurisdiction_level(self) -> None:
        base = _base()
        ov_country_level = _override(
            id="ov-sg-mgr",
            jurisdiction_countries=["SG"],
            employee_level="manager",
            amount_value=9500,
            currency_code="SGD",
        )
        ov_full = _override(
            id="ov-sg-mgr-perm",
            jurisdiction_countries=["SG"],
            employee_level="manager",
            assignment_type="permanent",
            amount_value=12000,
            currency_code="SGD",
        )
        eff, ov_id = resolve_effective_benefit(
            base,
            [ov_country_level, ov_full],
            {"country": "SG", "employee_level": "manager", "assignment_type": "permanent"},
        )
        self.assertEqual(ov_id, "ov-sg-mgr-perm")
        self.assertEqual(eff["amount_value"], 12000)

    def test_non_matching_level_disqualifies(self) -> None:
        base = _base()
        # Override targets manager only — director should NOT match.
        ov = _override(
            id="ov-sg-mgr",
            jurisdiction_countries=["SG"],
            employee_level="manager",
            amount_value=9500,
        )
        eff, ov_id = resolve_effective_benefit(
            base, [ov], {"country": "SG", "employee_level": "director"}
        )
        self.assertEqual(eff["amount_value"], 5000)  # base
        self.assertFalse(eff["override_applied"])
        self.assertIsNone(ov_id)

    def test_non_matching_assignment_type_disqualifies(self) -> None:
        base = _base()
        ov = _override(
            id="ov-sg-perm",
            jurisdiction_countries=["SG"],
            assignment_type="permanent",
            amount_value=10000,
        )
        eff, ov_id = resolve_effective_benefit(
            base, [ov], {"country": "SG", "assignment_type": "short_term"}
        )
        self.assertFalse(eff["override_applied"])
        self.assertIsNone(ov_id)

    def test_country_not_in_list_disqualifies(self) -> None:
        base = _base()
        ov = _override(
            id="ov-sea",
            jurisdiction_countries=["SG", "MY"],
            amount_value=8000,
        )
        eff, ov_id = resolve_effective_benefit(base, [ov], {"country": "JP"})
        self.assertFalse(eff["override_applied"])
        self.assertIsNone(ov_id)

    def test_grouped_country_list_matches_each_member(self) -> None:
        base = _base()
        ov = _override(
            id="ov-sea",
            jurisdiction_countries=["SG", "MY", "TH"],
            amount_value=8000,
            currency_code="SGD",
        )
        for country in ("SG", "MY", "TH"):
            eff, ov_id = resolve_effective_benefit(
                base, [ov], {"country": country, "employee_level": None}
            )
            self.assertEqual(ov_id, "ov-sea", country)
            self.assertEqual(eff["amount_value"], 8000)

    def test_null_fields_inherit_from_base(self) -> None:
        # HR overrides only the markdown for SG; the cap stays at base.
        base = _base()
        ov = _override(
            id="ov-sg-md",
            jurisdiction_countries=["SG"],
            amount_value=None,  # NULL = inherit
            currency_code=None,
            reimbursement_md="Singapore-specific reimbursement note.",
        )
        eff, ov_id = resolve_effective_benefit(base, [ov], {"country": "SG"})
        self.assertTrue(eff["override_applied"])
        self.assertEqual(ov_id, "ov-sg-md")
        # Cap inherited from base.
        self.assertEqual(eff["amount_value"], 5000)
        self.assertEqual(eff["currency_code"], "USD")
        # Markdown overridden.
        self.assertEqual(eff["reimbursement_md"], "Singapore-specific reimbursement note.")

    def test_tiebreak_by_display_order(self) -> None:
        # Two overrides with identical specificity (both wildcards) — pick
        # the higher display_order.
        base = _base()
        ov_low = _override(
            id="ov-low",
            jurisdiction_countries=["SG"],
            amount_value=7000,
            display_order=1,
        )
        ov_high = _override(
            id="ov-high",
            jurisdiction_countries=["SG"],
            amount_value=8000,
            display_order=5,
        )
        eff, ov_id = resolve_effective_benefit(
            base, [ov_low, ov_high], {"country": "SG"}
        )
        self.assertEqual(ov_id, "ov-high")
        self.assertEqual(eff["amount_value"], 8000)

    def test_tiebreak_by_updated_at_when_display_order_ties(self) -> None:
        base = _base()
        ov_old = _override(
            id="ov-old",
            jurisdiction_countries=["SG"],
            amount_value=7000,
            display_order=0,
            updated_at="2026-01-01T00:00:00Z",
        )
        ov_new = _override(
            id="ov-new",
            jurisdiction_countries=["SG"],
            amount_value=8000,
            display_order=0,
            updated_at="2026-04-27T00:00:00Z",
        )
        eff, ov_id = resolve_effective_benefit(
            base, [ov_old, ov_new], {"country": "SG"}
        )
        self.assertEqual(ov_id, "ov-new")

    def test_override_id_round_trips_as_str(self) -> None:
        base = _base()
        ov = _override(id=12345, jurisdiction_countries=["SG"], amount_value=8000)
        eff, ov_id = resolve_effective_benefit(base, [ov], {"country": "SG"})
        self.assertEqual(ov_id, "12345")
        self.assertEqual(eff["override_id"], "12345")

    def test_country_normalization_case_insensitive(self) -> None:
        base = _base()
        ov = _override(jurisdiction_countries=["sg"], amount_value=8000)
        eff, ov_id = resolve_effective_benefit(
            base, [ov], {"country": "sg"}  # lower-case input
        )
        self.assertTrue(eff["override_applied"])

    def test_json_encoded_country_list_from_sqlite(self) -> None:
        # SQLite mirror stores text[] as JSON-encoded TEXT. Resolver must
        # handle either shape.
        base = _base()
        ov = _override(
            id="ov-sqlite",
            jurisdiction_countries='["SG","MY"]',  # type: ignore[arg-type]
            amount_value=8000,
        )
        eff, ov_id = resolve_effective_benefit(base, [ov], {"country": "MY"})
        self.assertEqual(ov_id, "ov-sqlite")


# --- resolve_many ------------------------------------------------------------


class ResolveManyTests(unittest.TestCase):
    def test_groups_apply_correctly(self) -> None:
        base_a = _base(id="a", amount_value=5000)
        base_b = _base(id="b", benefit_key="housing", amount_value=10000)
        overrides = {
            "a": [
                _override(
                    id="ov-a-sg",
                    benefit_row_id="a",
                    jurisdiction_countries=["SG"],
                    amount_value=8000,
                )
            ],
            # b has no overrides for SG; should pass through.
        }
        out = resolve_many(
            [base_a, base_b],
            overrides,
            {"country": "SG", "employee_level": None},
        )
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["amount_value"], 8000)
        self.assertTrue(out[0]["override_applied"])
        self.assertEqual(out[1]["amount_value"], 10000)
        self.assertFalse(out[1]["override_applied"])

    def test_empty_overrides_dict_passes_through(self) -> None:
        base_a = _base(id="a")
        out = resolve_many([base_a], {}, {"country": "SG"})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["amount_value"], 5000)


if __name__ == "__main__":
    unittest.main()
