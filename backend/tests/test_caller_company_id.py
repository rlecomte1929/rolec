"""WS1 Task 1.3 — shared ``caller_company_id`` (auth_deps).

Three behaviour buckets, matching the eight router call sites:

- optional (no raise): admin_corrections, ai_decisions, ocr, hr_catalog optional
- required: employee_quotes, hr_catalog, research_requests, hr_company_invites
- required + include_case_assignment: exception_requests

Where the old router bodies were already hr_users-first, they are kept here
as oracles so a later change to the helper cannot silently diverge.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional

import pytest
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi import HTTPException  # noqa: E402

from backend.app.auth_deps import caller_company_id, get_org_id_for_hr_user  # noqa: E402
from backend.app.routers import (  # noqa: E402
    admin_corrections,
    ai_decisions,
    employee_quotes,
    exception_requests,
    hr_catalog,
    ocr,
    research_requests,
)
from backend.database import db  # noqa: E402

LEGACY_HR = {"id": "seed-hr-testingapril", "role": "HR", "email": "hr@testingapril.com"}
COMPANY = "company-A"
DETAIL_QUOTES = "No company linked to this profile."
DETAIL_CATALOG = "No company linked to this profile — HR curation needs a tenant."
DETAIL_RESEARCH = "No company associated with this user"
DETAIL_EXCEPTIONS = (
    "No company linked to this profile — exception requests need a tenant."
)


def _oracle_hr_users_first(user: Dict[str, Any]) -> Optional[str]:
    """Pre-consolidation body from hr_catalog optional / admin_corrections."""
    uid = user.get("id")
    company_id = (db.get_hr_company_id(uid) if uid else None) or (
        db.get_profile_record(uid) or {}
    ).get("company_id") or user.get("company")
    return str(company_id) if company_id else None


class TestOptionalBucket:
    def test_legacy_hr_resolves_via_hr_users_only(self):
        with mock.patch.object(db, "get_hr_company_id", return_value=COMPANY) as hr, \
             mock.patch.object(db, "get_profile_record", return_value=None):
            user = dict(LEGACY_HR)
            assert caller_company_id(user) == COMPANY
            assert admin_corrections._caller_company_id(user) == COMPANY
            assert ai_decisions._caller_company_id(user) == COMPANY
            assert ocr._caller_company_id(user) == COMPANY
            assert hr_catalog._caller_company_id_optional(user) == COMPANY
            assert _oracle_hr_users_first(user) == COMPANY
        hr.assert_called_with("seed-hr-testingapril")

    def test_unresolvable_returns_none(self):
        with mock.patch.object(db, "get_hr_company_id", return_value=None), \
             mock.patch.object(db, "get_profile_record", return_value=None):
            user = dict(LEGACY_HR)
            assert caller_company_id(user) is None
            assert _oracle_hr_users_first(user) is None


class TestRequiredBucket:
    def test_legacy_hr_resolves_via_hr_users_only(self):
        with mock.patch.object(db, "get_hr_company_id", return_value=COMPANY), \
             mock.patch.object(db, "get_profile_record", return_value=None):
            user = dict(LEGACY_HR)
            assert caller_company_id(user, required=True, detail=DETAIL_QUOTES) == COMPANY
            assert employee_quotes._caller_company_id(user) == COMPANY
            assert hr_catalog._caller_company_id(user) == COMPANY
            assert research_requests._caller_company_id(user) == COMPANY

    def test_unresolvable_raises_403_with_site_detail(self):
        with mock.patch.object(db, "get_hr_company_id", return_value=None), \
             mock.patch.object(db, "get_profile_record", return_value=None):
            user = dict(LEGACY_HR)
            assert caller_company_id(user, required=False) is None
            with pytest.raises(HTTPException) as ei:
                caller_company_id(user, required=True, detail=DETAIL_QUOTES)
            assert ei.value.status_code == 403
            assert ei.value.detail == DETAIL_QUOTES
            with pytest.raises(HTTPException) as ei:
                employee_quotes._caller_company_id(user)
            assert ei.value.detail == DETAIL_QUOTES
            with pytest.raises(HTTPException) as ei:
                hr_catalog._caller_company_id(user)
            assert ei.value.detail == DETAIL_CATALOG
            with pytest.raises(HTTPException) as ei:
                research_requests._caller_company_id(user)
            assert ei.value.detail == DETAIL_RESEARCH


class TestAssignmentBucket:
    def test_legacy_hr_resolves_via_hr_users_without_assignment(self):
        with mock.patch.object(db, "get_hr_company_id", return_value=COMPANY) as hr, \
             mock.patch.object(db, "get_profile_record", return_value=None), \
             mock.patch.object(db, "get_assignment_for_employee") as asg:
            user = dict(LEGACY_HR)
            assert caller_company_id(
                user, required=True, include_case_assignment=True, detail=DETAIL_EXCEPTIONS
            ) == COMPANY
            assert exception_requests._caller_company_id(user) == COMPANY
        hr.assert_called_with("seed-hr-testingapril")
        asg.assert_not_called()

    def test_employee_resolves_via_assignment(self):
        emp = {"id": "seed-emp-testingapril", "role": "EMPLOYEE"}
        with mock.patch.object(db, "get_hr_company_id", return_value=None), \
             mock.patch.object(db, "get_profile_record", return_value=None), \
             mock.patch.object(
                 db, "get_assignment_for_employee", return_value={"id": "asg-1"}
             ) as asg, \
             mock.patch.object(
                 db, "get_company_id_for_assignment_id", return_value="comp-asg"
             ):
            assert caller_company_id(
                emp, required=True, include_case_assignment=True, detail=DETAIL_EXCEPTIONS
            ) == "comp-asg"
            assert exception_requests._caller_company_id(emp) == "comp-asg"
            asg.assert_called_with("seed-emp-testingapril", request_id=None)
            # Optional helper must not walk assignments.
            assert caller_company_id(emp) is None

    def test_unresolvable_403_not_500_when_lookups_raise(self):
        with mock.patch.object(
            db, "get_hr_company_id", side_effect=Exception("no hr_users table")
        ), mock.patch.object(db, "get_profile_record", return_value=None), mock.patch.object(
            db, "get_assignment_for_employee", side_effect=Exception("boom")
        ):
            with pytest.raises(HTTPException) as ei:
                caller_company_id(
                    {"id": "u"},
                    required=True,
                    include_case_assignment=True,
                    detail=DETAIL_EXCEPTIONS,
                )
            assert ei.value.status_code == 403
            assert caller_company_id({"id": "u"}) is None


def test_get_org_id_for_hr_user_still_returns_empty_string():
    """Different contract — must not be rewritten to return None."""
    with mock.patch.object(db, "get_hr_company_id", return_value=None):
        assert get_org_id_for_hr_user(user=dict(LEGACY_HR)) == ""
