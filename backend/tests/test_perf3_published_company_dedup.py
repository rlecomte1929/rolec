"""
[AIQ-1014/PERF-3] GET /api/hr/policy-config/published resolved the HR company
twice (once for the onboarding check, once via _policy_matrix_company_hr). Prove
the handler now resolves it ONCE for non-admin HR (no redundant re-query), while
preserving the empty-onboarding and admin-override behaviours exactly.

Calls the route function directly with a fake user + patched module helpers, so
no app harness / live DB is needed.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.app.routers import policy_config as pc


def _call(user):
    return pc.hr_get_policy_config_published(
        companyId=None,
        assignmentType=None,
        familyStatus=None,
        employeeLevel=None,
        effectiveRowsOnly=False,
        user=user,
    )


class PublishedCompanyDedupTests(unittest.TestCase):
    def test_non_admin_hr_resolves_company_once(self):
        user = {"id": "hr-1", "role": "HR", "is_admin": False}
        with (
            patch.object(pc, "_get_hr_company_id", return_value="co-1") as m_get,
            patch.object(pc, "_policy_matrix_company_hr") as m_resolve,
            patch.object(pc.policy_config_matrix_svc, "get_published_payload", return_value={"ok": True}) as m_pay,
        ):
            out = _call(user)
        self.assertEqual(out, {"ok": True})
        m_get.assert_called_once()        # resolved once...
        m_resolve.assert_not_called()     # ...and NOT re-resolved (the dedup)
        self.assertEqual(m_pay.call_args.args[0], "co-1")  # right company passed through

    def test_non_admin_hr_no_company_returns_onboarding(self):
        user = {"id": "hr-x", "role": "HR", "is_admin": False}
        with (
            patch.object(pc, "_get_hr_company_id", return_value=None),
            patch.object(pc.policy_config_matrix_svc, "empty_onboarding_payload", return_value={"onboarding": True}) as m_onb,
            patch.object(pc.policy_config_matrix_svc, "get_published_payload") as m_pay,
        ):
            out = _call(user)
        self.assertEqual(out, {"onboarding": True})
        m_onb.assert_called_once()
        m_pay.assert_not_called()         # no company → never builds the payload

    def test_admin_uses_override_aware_path(self):
        user = {"id": "admin-1", "role": "ADMIN", "is_admin": True}
        with (
            patch.object(pc, "_get_hr_company_id") as m_get,
            patch.object(pc, "_policy_matrix_company_hr", return_value="co-admin") as m_resolve,
            patch.object(pc.policy_config_matrix_svc, "get_published_payload", return_value={"ok": True}) as m_pay,
        ):
            out = _call(user)
        self.assertEqual(out, {"ok": True})
        m_resolve.assert_called_once()    # admin keeps the override-aware resolver
        m_get.assert_not_called()         # admin never pays the HR-company query
        self.assertEqual(m_pay.call_args.args[0], "co-admin")


if __name__ == "__main__":
    unittest.main()
