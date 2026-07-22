"""AIQ-1527 — the budget summary must not claim "within budget" having compared nothing.

THE BUG
-------
`_budget_categories_from_policy_config` hardcoded:

    "estimated_amount": None,
    "status": "within_budget" if total is not None else "no_cap",

So the endpoint reported **within_budget** whenever a CAP existed. There was no estimate — the
line above set it to None. HR and the employee were shown a green tick derived from nothing, and
they act on it.

Same class as the corridor lock, the nationality routing and the empty RFQ brief: the system
asserting something it never checked.

Only 3 of 31 `case_services` rows carry an `estimated_cost` in prod, so the honest answer is
usually "we don't know yet" — which is fine, and far better than a fake tick.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import cases_read  # noqa: E402

status = cases_read._budget_status  # the real shipped decision, not a copy of it


class StatusHonestyTests(unittest.TestCase):
    def test_a_cap_with_NO_estimate_is_never_within_budget(self):
        # THE REGRESSION GUARD. This is exactly what shipped: a cap existed, no cost was ever
        # read, and the user was told "within_budget".
        self.assertEqual(status(5000, "EUR", None, None), "no_estimate")

    def test_no_cap_is_no_cap(self):
        self.assertEqual(status(None, None, None, None), "no_cap")
        # …even when we DO have an estimate — there is nothing to compare it against.
        self.assertEqual(status(None, None, 4200, "EUR"), "no_cap")

    def test_a_real_comparison_is_made_when_both_numbers_exist(self):
        self.assertEqual(status(5000, "EUR", 4200, "EUR"), "within_budget")
        self.assertEqual(status(5000, "EUR", 6100, "EUR"), "over_budget")

    def test_an_estimate_exactly_ON_the_cap_is_within_budget(self):
        self.assertEqual(status(5000, "EUR", 5000, "EUR"), "within_budget")

    def test_a_currency_mismatch_REFUSES_to_rank_rather_than_inventing_an_fx_rate(self):
        # Mirrors policy_config_cap_compare, which returns supported_comparison=False on a
        # currency mismatch rather than guessing. There is no FX conversion anywhere.
        self.assertEqual(status(5000, "EUR", 4200, "USD"), "not_comparable")

    def test_a_zero_estimate_is_an_ANSWER_not_a_missing_one(self):
        self.assertEqual(status(5000, "EUR", 0, "EUR"), "within_budget")


class EstimateReaderTests(unittest.TestCase):
    def test_estimates_are_read_from_case_services(self):
        db = mock.MagicMock()
        conn = db.engine.connect.return_value.__enter__.return_value
        conn.execute.return_value.mappings.return_value.all.return_value = [
            {"service_key": "movers", "estimated_cost": 4250, "currency": "EUR"},
        ]
        with mock.patch.object(cases_read, "main_db", db):
            out = cases_read._case_service_estimates("case-1")
        self.assertEqual(out["movers"]["amount"], 4250.0)
        self.assertEqual(out["movers"]["currency"], "EUR")

    def test_a_db_failure_degrades_to_UNKNOWN_never_to_a_green_tick(self):
        db = mock.MagicMock()
        db.engine.connect.side_effect = RuntimeError("db down")
        with mock.patch.object(cases_read, "main_db", db):
            self.assertEqual(cases_read._case_service_estimates("case-1"), {})
        # {} means every category resolves to "no_estimate" — never "within_budget".
        self.assertEqual(status(5000, "EUR", None, None), "no_estimate")

    def test_no_case_id_is_empty(self):
        self.assertEqual(cases_read._case_service_estimates(""), {})


class SourceContractTests(unittest.TestCase):
    def test_the_fake_green_tick_is_GONE_from_the_source(self):
        """Pin the literal defect so it cannot return by copy-paste:
        `"status": "within_budget" if total is not None else "no_cap"`."""
        import inspect

        src = inspect.getsource(cases_read._budget_categories_from_policy_config)
        self.assertNotIn('"within_budget" if total is not None', src)
        self.assertNotIn('"estimated_amount": None', src)


if __name__ == "__main__":
    unittest.main()
