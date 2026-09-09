"""
AIQ-861 — AI-decisions audit company-resolution regression guard.

The EU AI Act Art.14 audit surface (GET /api/ai/decisions) 403'd with
"No company linked to this profile" for a legitimate HR whose id is a LEGACY
text id (e.g. ``seed-hr-testingapril``) — even though the same HR resolves
their company everywhere else. Root cause: ai_decisions._caller_company_id
used the profiles-only path, which returns None for non-UUID legacy ids and
never consulted ``hr_users``. The fix adds the ``db.get_hr_company_id``
fallback (same resolver as command-center / exceptions / AIQ-862).

These tests pin the fix AND that it resolves only the caller's OWN company
(no cross-tenant widening). DB-free: ``db`` methods are monkeypatched.
"""
from __future__ import annotations

import os
import sys

from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.database import db  # noqa: E402
from backend.app.routers.ai_decisions import _caller_company_id  # noqa: E402

LEGACY_HR = {"id": "seed-hr-testingapril", "role": "HR", "email": "hr@testingapril.com"}


def test_legacy_hr_resolves_company_via_hr_users():
    # Pre-fix this returned None (profiles None, no session company) → 403.
    with mock.patch.object(db, "get_profile_record", return_value=None), \
         mock.patch.object(db, "get_hr_company_id", return_value="company-A") as m:
        assert _caller_company_id(dict(LEGACY_HR)) == "company-A"
    m.assert_called_once_with("seed-hr-testingapril")


def test_resolves_to_callers_own_company_only():
    # The resolver passes the caller's own id to get_hr_company_id, which reads
    # hr_users for that profile_id — so it can only ever return the caller's
    # company, never another tenant's. (Isolation guarantee.)
    seen = {}

    def fake_hr_company(pid):
        seen["pid"] = pid
        return "company-A"

    with mock.patch.object(db, "get_profile_record", return_value=None), \
         mock.patch.object(db, "get_hr_company_id", side_effect=fake_hr_company):
        assert _caller_company_id(dict(LEGACY_HR)) == "company-A"
    assert seen["pid"] == "seed-hr-testingapril"


def test_none_when_truly_unlinked():
    with mock.patch.object(db, "get_profile_record", return_value=None), \
         mock.patch.object(db, "get_hr_company_id", return_value=None):
        assert _caller_company_id(dict(LEGACY_HR)) is None


def test_profile_path_used_when_hr_users_empty():
    uuid_hr = {"id": "11111111-1111-1111-1111-111111111111", "role": "HR"}
    with mock.patch.object(db, "get_profile_record", return_value={"company_id": "company-X"}), \
         mock.patch.object(db, "get_hr_company_id", return_value=None):
        assert _caller_company_id(dict(uuid_hr)) == "company-X"


def test_hr_users_wins_over_profile():
    uuid_hr = {"id": "11111111-1111-1111-1111-111111111111", "role": "HR"}
    with mock.patch.object(db, "get_profile_record", return_value={"company_id": "company-X"}), \
         mock.patch.object(db, "get_hr_company_id", return_value="company-A"):
        assert _caller_company_id(dict(uuid_hr)) == "company-A"


def test_session_company_claim_used_when_hr_users_and_profile_empty():
    user = dict(LEGACY_HR, company="company-claim")
    with mock.patch.object(db, "get_profile_record", return_value=None), \
         mock.patch.object(db, "get_hr_company_id", return_value=None):
        assert _caller_company_id(user) == "company-claim"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
