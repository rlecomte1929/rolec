"""
Regression tests for GET /api/employee/policy/caps (get_employee_policy_caps).

[AIQ-999 / POLICY-CAPS] The handler used to read a global static policy file
and fall back to hardcoded defaults (housing $5k / movers $10k / schools $20k /
immigration $4k), returning the same placeholder for every employee regardless
of whether their company published a policy. It now resolves the caller's
assignment and reads the same per-assignment published policy the
comparison/policy-budget endpoints use, returning honest null caps when there
is no published policy.

Direct-call pattern: the handler is called directly with a minimal Request and
the per-assignment resolver + assignment lookup mocked, so the caps mapping is
exercised without standing up the full resolution pipeline.
"""
from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("POLICY_ASSISTANT_LLM", "mock")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend import main as main_module  # noqa: E402


def _request():
    return types.SimpleNamespace(state=types.SimpleNamespace(request_id="test-req"))


_EMPLOYEE = {"id": "emp-1", "role": "EMPLOYEE"}

# Hardcoded placeholder caps the old handler returned for everyone.
_FAKE_DEFAULTS = {5000, 10000, 20000, 4000}


class EmployeePolicyCapsTests(unittest.TestCase):
    def _call(self, **kwargs):
        return main_module.get_employee_policy_caps(
            request=_request(),
            display_currency=kwargs.get("display_currency"),
            user=kwargs.get("user", _EMPLOYEE),
        )

    def test_no_assignment_returns_honest_empty(self) -> None:
        with mock.patch.object(
            main_module.db, "get_assignment_for_employee", return_value=None
        ):
            payload = self._call()
        self.assertFalse(payload["has_policy"])
        self.assertIsNone(payload["housing_monthly_usd"])
        self.assertIsNone(payload["movers_usd"])
        self.assertIsNone(payload["schools_usd"])
        self.assertIsNone(payload["immigration_usd"])
        # Crucial regression: none of the old hardcoded defaults leak through.
        self.assertFalse(_FAKE_DEFAULTS & set(
            v for v in payload.values() if isinstance(v, (int, float))
        ))

    def test_no_published_policy_returns_honest_empty(self) -> None:
        with mock.patch.object(
            main_module.db,
            "get_assignment_for_employee",
            return_value={"id": "asg-1"},
        ), mock.patch.object(
            main_module,
            "_resolve_published_policy_for_employee",
            return_value={"has_policy": False, "benefits": []},
        ):
            payload = self._call()
        self.assertFalse(payload["has_policy"])
        self.assertIsNone(payload["housing_monthly_usd"])
        self.assertIsNone(payload["immigration_usd"])

    def test_published_policy_returns_real_caps(self) -> None:
        benefits = [
            {"benefit_key": "temporary_housing", "included": True, "max_value": 3000, "currency": "USD"},
            {"benefit_key": "shipment", "included": True, "max_value": 8000},
            {"benefit_key": "schooling", "included": True, "max_value": 15000},
        ]
        with mock.patch.object(
            main_module.db,
            "get_assignment_for_employee",
            return_value={"id": "asg-1"},
        ), mock.patch.object(
            main_module,
            "_resolve_published_policy_for_employee",
            return_value={"has_policy": True, "benefits": benefits},
        ):
            payload = self._call()
        self.assertTrue(payload["has_policy"])
        self.assertEqual(payload["housing_monthly_usd"], 3000)
        self.assertEqual(payload["movers_usd"], 8000)
        self.assertEqual(payload["schools_usd"], 15000)
        # No immigration benefit in the policy → honest null, not a $4k default.
        self.assertIsNone(payload["immigration_usd"])

    def test_display_currency_converts_and_is_null_safe(self) -> None:
        benefits = [
            {"benefit_key": "temporary_housing", "included": True, "max_value": 3000, "currency": "USD"},
        ]
        with mock.patch.object(
            main_module.db,
            "get_assignment_for_employee",
            return_value={"id": "asg-1"},
        ), mock.patch.object(
            main_module,
            "_resolve_published_policy_for_employee",
            return_value={"has_policy": True, "benefits": benefits},
        ):
            payload = self._call(display_currency="EUR")
        self.assertEqual(payload["display_currency"], "EUR")
        self.assertIn("caps_display", payload)
        # housing present → numeric display; absent services → null (not a default).
        self.assertIsInstance(payload["caps_display"]["housing_monthly"], (int, float))
        self.assertIsNone(payload["caps_display"]["movers"])
        self.assertIsNone(payload["caps_display"]["immigration"])

    def test_display_currency_on_no_policy_is_all_null(self) -> None:
        with mock.patch.object(
            main_module.db, "get_assignment_for_employee", return_value=None
        ):
            payload = self._call(display_currency="GBP")
        self.assertFalse(payload["has_policy"])
        self.assertEqual(payload["display_currency"], "GBP")
        for v in payload["caps_display"].values():
            self.assertIsNone(v)


if __name__ == "__main__":
    unittest.main()
