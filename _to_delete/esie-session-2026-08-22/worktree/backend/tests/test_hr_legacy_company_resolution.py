"""
AIQ-862 — Legacy HR company-resolution regression guard.

A legitimate HR with a LEGACY text id (e.g. ``seed-hr-testingapril``, not a
UUID) viewing their own company's case was denied on three endpoints:
  - GET /api/hr/cases/{id}/providers   (get_org_id_for_hr_user → org_id="")
  - GET /api/hr/quote-requests         (_caller_company_id → 403)
  - GET /api/hr/{companyId}/exec-summary (_authorize_company → 403)

Root cause: all three resolved company via profiles-only / session-claim, which
returns nothing for non-UUID legacy ids. The fix routes them through
``db.get_hr_company_id`` (the hr_users-aware resolver). These tests pin that
behaviour AND assert the fix does not widen access (cross-company still 403).

DB-free: ``db`` methods are monkeypatched, so no engine/network is needed.
"""
from __future__ import annotations

import os
import sys

import pytest
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi import HTTPException  # noqa: E402

from backend.database import db  # noqa: E402
from backend.app.auth_deps import get_org_id_for_hr_user  # noqa: E402
from backend.app.routers.employee_quotes import _caller_company_id  # noqa: E402
from backend.app.routers.nlg import _authorize_company  # noqa: E402

# Legacy text id (not UUID-castable) — the case that used to break.
LEGACY_HR = {"id": "seed-hr-testingapril", "role": "HR", "email": "hr@testingapril.com"}


# --- get_org_id_for_hr_user (providers + ~25 other HR endpoints) -------------

def test_get_org_id_resolves_legacy_hr_via_hr_users():
    # Pre-fix this returned "" (profiles None, no session company) → mis-scoped.
    with mock.patch.object(db, "get_profile_record", return_value=None), \
         mock.patch.object(db, "get_hr_company_id", return_value="company-A") as m:
        assert get_org_id_for_hr_user(user=dict(LEGACY_HR)) == "company-A"
    m.assert_called_once_with("seed-hr-testingapril")


def test_get_org_id_falls_back_to_session_company_claim():
    user = dict(LEGACY_HR, company="company-claim")
    with mock.patch.object(db, "get_hr_company_id", return_value=None):
        assert get_org_id_for_hr_user(user=user) == "company-claim"


def test_get_org_id_empty_when_no_company_anywhere():
    with mock.patch.object(db, "get_hr_company_id", return_value=None):
        assert get_org_id_for_hr_user(user=dict(LEGACY_HR)) == ""


# --- _caller_company_id (HR quote-requests) ---------------------------------

def test_caller_company_id_resolves_legacy_hr():
    with mock.patch.object(db, "get_profile_record", return_value=None), \
         mock.patch.object(db, "get_hr_company_id", return_value="company-A"):
        assert _caller_company_id(dict(LEGACY_HR)) == "company-A"


def test_caller_company_id_403_only_when_truly_unlinked():
    with mock.patch.object(db, "get_profile_record", return_value=None), \
         mock.patch.object(db, "get_hr_company_id", return_value=None):
        with pytest.raises(HTTPException) as ei:
            _caller_company_id(dict(LEGACY_HR))
    assert ei.value.status_code == 403


# --- _authorize_company (exec-summary) --------------------------------------

def test_authorize_company_allows_legacy_hr_on_own_company():
    with mock.patch.object(db, "get_hr_company_id", return_value="company-A"):
        # No exception == authorized.
        _authorize_company(dict(LEGACY_HR), "company-A")


def test_authorize_company_still_denies_cross_company_after_resolution():
    # SECURITY: resolving the caller's real company must NOT grant access to a
    # different company. company-A caller hitting company-B → 403.
    with mock.patch.object(db, "get_hr_company_id", return_value="company-A"):
        with pytest.raises(HTTPException) as ei:
            _authorize_company(dict(LEGACY_HR), "company-B")
    assert ei.value.status_code == 403


def test_authorize_company_unresolvable_hr_denied():
    with mock.patch.object(db, "get_hr_company_id", return_value=None):
        with pytest.raises(HTTPException) as ei:
            _authorize_company(dict(LEGACY_HR), "company-A")
    assert ei.value.status_code == 403


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
