"""
SEC-MUT-DRAIN — auth on the previously-unauthenticated support automation and
A/B-test mutation endpoints.

  • support.verify_support_automation_secret enforces X-Support-Automation-Secret
    when SUPPORT_AUTOMATION_SECRET is configured (fail-open when blank so local
    dev works; fail-closed once set).
  • ab_tests.promote_variant / rollback_flag require an admin session.

These are signature/behaviour-level tests (no app mount) per the project's
app-mounted-harness caveat.
"""
from __future__ import annotations

import inspect
import unittest
from unittest import mock

from fastapi import HTTPException

from backend.app.routers import ab_tests, support


class SupportAutomationSecretTests(unittest.TestCase):
    def test_fail_open_when_secret_unset(self):
        """Blank secret → dependency is a no-op (local dev / not-yet-configured)."""
        with mock.patch.object(support, "SUPPORT_AUTOMATION_SECRET", ""):
            self.assertIsNone(support.verify_support_automation_secret(secret="anything"))
            self.assertIsNone(support.verify_support_automation_secret(secret=None))

    def test_rejects_missing_or_wrong_secret_when_configured(self):
        with mock.patch.object(support, "SUPPORT_AUTOMATION_SECRET", "s3cr3t"):
            for bad in (None, "", "wrong"):
                with self.assertRaises(HTTPException) as ctx:
                    support.verify_support_automation_secret(secret=bad)
                self.assertEqual(ctx.exception.status_code, 401)

    def test_accepts_matching_secret_when_configured(self):
        with mock.patch.object(support, "SUPPORT_AUTOMATION_SECRET", "s3cr3t"):
            self.assertIsNone(support.verify_support_automation_secret(secret="s3cr3t"))


def _dep_names(func):
    """Names of the Depends() callables in a handler's signature defaults."""
    names = []
    for p in inspect.signature(func).parameters.values():
        dep = getattr(p.default, "dependency", None)
        if dep is not None:
            names.append(getattr(dep, "__name__", str(dep)))
    return names


class AbTestAdminAuthTests(unittest.TestCase):
    def test_promote_requires_admin(self):
        self.assertIn("require_admin", _dep_names(ab_tests.promote_variant))

    def test_rollback_requires_admin(self):
        self.assertIn("require_admin", _dep_names(ab_tests.rollback_flag))


if __name__ == "__main__":
    unittest.main()
