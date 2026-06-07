"""
UIAUDIT-G14 — company-resolution bug-class sweep.

Several HR-scoped endpoints resolved the acting HR user's own company via the
profiles/user path only (`get_profile_record(uid).company_id` / `user.get("company")`),
which is NULL for legacy/text HR ids (e.g. seed-hr-testingapril) even though their
`hr_users` row holds the company. That wrongly 403/400'd or emptied data for real
demo/seed HR accounts. Every such site must try `db.get_hr_company_id(uid)` first.

These tests pin the per-module resolution helpers. The remaining fixed sites in
backend/main.py (company-profile logo, preferred-suppliers, policy-assistant
rag-query) and backend/app/routers/cases_read.py route their resolution through
the already-tested `_get_hr_company_id` / `db.get_hr_company_id` helper.

Most helpers import the db singleton (`from ...database import db`), so we patch the
shared backend.database.db object they resolve to — same approach as
test_providers_company_resolution.py (G4).
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi import HTTPException

from backend.database import db as real_db
from backend.app.routers import hr_catalog, hr_policies, hr_rfq, services_state, branding
from backend.app.services import policy_canonical_access

_COMPANY = "c0000000-0000-0000-0000-000000000001"
_LEGACY_HR = {"id": "seed-hr-testingapril", "role": "HR", "company": None}


def _patch_legacy_hr():
    """hr_users links the legacy HR to a company; profiles.company_id is NULL."""
    return (
        mock.patch.object(real_db, "get_hr_company_id", return_value=_COMPANY),
        mock.patch.object(
            real_db, "get_profile_record",
            return_value={"id": "seed-hr-testingapril", "company_id": None, "email": "hr@x.com"},
        ),
    )


def _patch_no_company():
    return (
        mock.patch.object(real_db, "get_hr_company_id", return_value=None),
        mock.patch.object(real_db, "get_profile_record", return_value=None),
    )


class HrCatalogResolution(unittest.TestCase):
    def test_caller_company_id_resolves_via_hr_users(self):
        p1, p2 = _patch_legacy_hr()
        with p1, p2:
            self.assertEqual(hr_catalog._caller_company_id(_LEGACY_HR), _COMPANY)

    def test_caller_company_id_optional_resolves_via_hr_users(self):
        p1, p2 = _patch_legacy_hr()
        with p1, p2:
            self.assertEqual(hr_catalog._caller_company_id_optional(_LEGACY_HR), _COMPANY)

    def test_caller_company_id_403_when_truly_no_company(self):
        p1, p2 = _patch_no_company()
        with p1, p2, self.assertRaises(HTTPException):
            hr_catalog._caller_company_id(_LEGACY_HR)

    def test_caller_company_id_optional_none_when_no_company(self):
        p1, p2 = _patch_no_company()
        with p1, p2:
            self.assertIsNone(hr_catalog._caller_company_id_optional(_LEGACY_HR))


class HrPoliciesResolution(unittest.TestCase):
    def test_org_id_resolves_via_hr_users(self):
        p1, p2 = _patch_legacy_hr()
        with p1, p2:
            self.assertEqual(hr_policies._org_id(_LEGACY_HR), _COMPANY)

    def test_org_id_403_when_truly_no_company(self):
        p1, p2 = _patch_no_company()
        with p1, p2, self.assertRaises(HTTPException):
            hr_policies._org_id(_LEGACY_HR)


class HrRfqResolution(unittest.TestCase):
    def test_require_hr_resolves_company_via_hr_users(self):
        p1, p2 = _patch_legacy_hr()
        with p1, p2:
            company_id, _email, _name = hr_rfq._require_hr(_LEGACY_HR)
            self.assertEqual(company_id, _COMPANY)


class ServicesStateResolution(unittest.TestCase):
    def test_caller_company_id_resolves_via_hr_users(self):
        p1, p2 = _patch_legacy_hr()
        with p1, p2:
            self.assertEqual(services_state._caller_company_id(_LEGACY_HR), _COMPANY)

    def test_caller_company_id_403_when_truly_no_company(self):
        p1, p2 = _patch_no_company()
        with p1, p2, self.assertRaises(HTTPException):
            services_state._caller_company_id(_LEGACY_HR)


class BrandingResolution(unittest.TestCase):
    def test_resolve_company_id_via_hr_users(self):
        # No company claim on the token → must resolve via hr_users, not 403.
        p1, p2 = _patch_legacy_hr()
        with p1, p2:
            self.assertEqual(branding._resolve_company_id(_LEGACY_HR), _COMPANY)

    def test_resolve_company_id_prefers_token_claim(self):
        # Unchanged behaviour: an explicit token company claim still wins.
        self.assertEqual(branding._resolve_company_id({"id": "x", "company": _COMPANY}), _COMPANY)


class PolicyCanonicalResolution(unittest.TestCase):
    def test_resolve_user_company_id_via_hr_users(self):
        fake_db = mock.Mock()
        fake_db.get_hr_company_id.return_value = _COMPANY
        fake_db.get_profile_record.return_value = {"id": "seed-hr-testingapril", "company_id": None}
        self.assertEqual(
            policy_canonical_access.resolve_user_company_id(_LEGACY_HR, fake_db), _COMPANY
        )

    def test_resolve_user_company_id_400_when_truly_no_company(self):
        fake_db = mock.Mock()
        fake_db.get_hr_company_id.return_value = None
        fake_db.get_profile_record.return_value = None
        with self.assertRaises(HTTPException):
            policy_canonical_access.resolve_user_company_id(_LEGACY_HR, fake_db)


if __name__ == "__main__":
    unittest.main()
