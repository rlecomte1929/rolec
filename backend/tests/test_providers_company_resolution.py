"""
UIAUDIT-G4 — provider-status-grid (and provider management) must resolve an HR's
company via hr_users first, so legacy/text HR ids (e.g. seed-hr-testingapril, whose
profiles.company_id is NULL) get their active cases instead of "0 active cases".

_caller_org_id() imports the db singleton locally (`from ...database import db`), so
we patch the shared backend.database.db object it resolves to.
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

from backend.app.routers import providers as providers_module
from backend.database import db as real_db

_COMPANY = "c0000000-0000-0000-0000-000000000001"


class ProviderCompanyResolutionTests(unittest.TestCase):
    def test_caller_org_id_resolves_via_hr_users(self):
        # Legacy/text HR id: profiles.company_id is NULL, but hr_users links them.
        user = {"id": "seed-hr-testingapril", "company": None}
        with mock.patch.object(real_db, "get_hr_company_id", return_value=_COMPANY), \
             mock.patch.object(real_db, "get_profile_record",
                               return_value={"id": "seed-hr-testingapril", "company_id": None}):
            self.assertEqual(providers_module._caller_org_id(user), _COMPANY)

    def test_caller_org_id_falls_back_to_profile(self):
        user = {"id": "uuid-hr", "company": None}
        with mock.patch.object(real_db, "get_hr_company_id", return_value=None), \
             mock.patch.object(real_db, "get_profile_record",
                               return_value={"id": "uuid-hr", "company_id": "comp-profile"}):
            self.assertEqual(providers_module._caller_org_id(user), "comp-profile")

    def test_caller_org_id_403_when_truly_no_company(self):
        user = {"id": "x", "company": None}
        with mock.patch.object(real_db, "get_hr_company_id", return_value=None), \
             mock.patch.object(real_db, "get_profile_record", return_value=None):
            with self.assertRaises(HTTPException):
                providers_module._caller_org_id(user)


if __name__ == "__main__":
    unittest.main()
