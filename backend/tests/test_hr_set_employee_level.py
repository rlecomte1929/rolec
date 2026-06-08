"""HR-sets-employee-level — the assign-time seniority band must flow to benefit
comparison. Covers the read path (extract_resolution_context resolves the band
HR writes into the case profile) + the assign request model accepting the field.

The DB write (db.set_case_employee_seniority → relocation_cases.profile_json) is
Postgres raw SQL; it's validated via a rollback-tx on prod (see the PR), not here.
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.policy_resolution import extract_resolution_context
from backend.schemas import AssignCaseRequest


def test_seniority_band_in_profile_resolves_to_employee_level():
    # The HR-set band lands at primaryApplicant.employer.seniorityBand; the resolver
    # must surface it as the canonical employee_level used for matrix targeting.
    profile = {"primaryApplicant": {"employer": {"seniorityBand": "manager"}}}
    ctx = extract_resolution_context({"id": "a1"}, {"id": "c1"}, profile, None)
    assert ctx["employee_level"] == "manager"


def test_director_band_normalizes():
    profile = {"primaryApplicant": {"employer": {"seniorityBand": "Director"}}}
    ctx = extract_resolution_context({"id": "a1"}, {"id": "c1"}, profile, None)
    assert ctx["employee_level"] == "director"


def test_no_band_leaves_level_unset():
    ctx = extract_resolution_context({"id": "a1"}, {"id": "c1"}, {}, None)
    assert ctx["employee_level"] is None


def test_assign_request_accepts_employee_level_camel_and_snake():
    assert AssignCaseRequest(employeeIdentifier="jane@x.com", employeeLevel="director").employeeLevel == "director"
    # legacy snake_case clients / test runner
    assert AssignCaseRequest(employee_email="jane@x.com", employee_level="vp").employeeLevel == "vp"


def test_assign_request_level_optional():
    assert AssignCaseRequest(employeeIdentifier="jane@x.com").employeeLevel is None
