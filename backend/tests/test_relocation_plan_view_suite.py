"""
Focused suite for the canonical relocation plan view (assembly + rules + auth hooks).

Uses ``build_relocation_plan_view_response`` so phase grouping, ordering, derivation,
next-action, and Pydantic contract are exercised without brittle HTTP snapshots.
Auth scenarios patch ``backend.main.db`` and call the same visibility helpers as the route.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.timeline_service import OPERATIONAL_TASK_DEFAULTS  # noqa: E402
from backend.relocation_plan_task_library import PHASE_ORDER  # noqa: E402
from backend.relocation_plan_view_schemas import (  # noqa: E402
    RelocationPlanViewResponse,
    RelocationPlanTaskStatus,
    RelocationPlanViewRole,
)
from backend.schemas import UserRole  # noqa: E402
from backend.services.relocation_plan_view_service import build_relocation_plan_view_response  # noqa: E402

def _mt_row(
    milestone_type: str,
    *,
    mid: Optional[str] = None,
    status: str = "pending",
    owner: Optional[str] = None,
    criticality: Optional[str] = None,
    sort_order: Optional[int] = None,
) -> Dict[str, Any]:
    spec = next((r for r in OPERATIONAL_TASK_DEFAULTS if r["milestone_type"] == milestone_type), None)
    title = spec["title"] if spec else milestone_type
    return {
        "id": mid or f"id-{milestone_type}",
        "milestone_type": milestone_type,
        "title": title,
        "status": status,
        "owner": owner or (spec["owner"] if spec else "employee"),
        "criticality": criticality or (spec["criticality"] if spec else "normal"),
        "sort_order": sort_order if sort_order is not None else (spec.get("sort_order", 0) if spec else 0),
    }


def full_case_milestones(
    status_by_type: Optional[Dict[str, str]] = None,
    *,
    include_provider_coordination: bool = True,
) -> List[Dict[str, Any]]:
    """
    One milestone per operational default (plus optional provider row), like a seeded case.
    ``status_by_type`` maps milestone_type → raw milestone status (pending/done/...).
    """
    st = status_by_type or {}
    rows: List[Dict[str, Any]] = []
    for spec in OPERATIONAL_TASK_DEFAULTS:
        mt = spec["milestone_type"]
        if mt == "task_provider_coordination" and not include_provider_coordination:
            continue
        rows.append(_mt_row(mt, status=st.get(mt, "pending")))
    return rows


def _task_by_code(resp: RelocationPlanViewResponse, code: str):
    for ph in resp.phases:
        for t in ph.tasks:
            if t.task_code == code:
                return t
    return None


def _next_action_task_code(resp: RelocationPlanViewResponse) -> Optional[str]:
    if resp.next_action is None:
        return None
    tid = resp.next_action.task_id
    for ph in resp.phases:
        for t in ph.tasks:
            if t.task_id == tid:
                return t.task_code
    return None


def _phase_keys_in_order(resp: RelocationPlanViewResponse) -> List[str]:
    return [p.phase_key for p in resp.phases]


def employee_profile_ready_for_passport_only(
    *,
    with_passport_scan: bool = False,
    with_family: bool = True,
) -> Dict[str, Any]:
    """Core + employment + route + optional family; passport left off unless flag set."""
    prof: Dict[str, Any] = {
        "primaryApplicant": {
            "fullName": "Alex Assignee",
            "nationality": "US",
            "employer": {"jobLevel": "IC4", "roleTitle": "Engineer"},
        },
        "movePlan": {"origin": "United States", "destination": "Germany"},
        "complianceDocs": {
            "hasEmploymentLetter": True,
        },
    }
    if with_passport_scan:
        prof["complianceDocs"]["hasPassportScans"] = True
    if with_family:
        prof["maritalStatus"] = "married"
        prof["spouse"] = {"fullName": "Sam Spouse"}
    return prof


def mock_db_with_services(selected: Optional[List[str]] = None) -> MagicMock:
    db = MagicMock()
    db.list_case_services.return_value = [
        {"service_key": k, "selected": True} for k in (selected or [])
    ]
    return db


def run_plan_view(
    *,
    milestones: List[Dict[str, Any]],
    profile: Dict[str, Any],
    viewer_role: str = "employee",
    db: Optional[MagicMock] = None,
    mobility_case_id: Optional[str] = None,
) -> RelocationPlanViewResponse:
    return build_relocation_plan_view_response(
        case_id="case-view-test",
        assignment_id="assign-view-test",
        milestones=milestones,
        profile_draft=profile,
        mobility_case_id=mobility_case_id,
        db=db or mock_db_with_services(),
        viewer_role=viewer_role,
        debug=False,
        request_id="req-suite",
    )


class RelocationPlanViewBusinessScenariosTests(unittest.TestCase):
    def test_employee_without_passport_next_action_is_upload_passport_copy(self) -> None:
        miles = full_case_milestones(
            {
                "task_profile_core": "done",
                "task_family_dependents": "done",
                "task_employment_letter": "done",
                "task_route_verify": "done",
                "task_passport_upload": "pending",
            }
        )
        prof = employee_profile_ready_for_passport_only(with_passport_scan=False, with_family=True)
        out = run_plan_view(milestones=miles, profile=prof, viewer_role="employee")
        self.assertIsNotNone(out.next_action)
        self.assertEqual(_next_action_task_code(out), "upload_passport_copy")

    def test_passport_on_file_marks_upload_passport_milestone_completed(self) -> None:
        miles = full_case_milestones({"task_profile_core": "done", "task_passport_upload": "pending"})
        prof = employee_profile_ready_for_passport_only(with_passport_scan=True, with_family=True)
        out = run_plan_view(milestones=miles, profile=prof, viewer_role="employee")
        t = _task_by_code(out, "upload_passport_copy")
        self.assertIsNotNone(t)
        assert t is not None
        self.assertEqual(t.status, RelocationPlanTaskStatus.COMPLETED)

    def test_submit_visa_stays_blocked_until_visa_pack_prereqs_and_pack_ready(self) -> None:
        """Passport missing → prepare_visa_pack blocked; submit depends on prepare → also blocked."""
        miles = full_case_milestones(
            {
                "task_profile_core": "done",
                "task_passport_upload": "pending",
                "task_employment_letter": "done",
                "task_route_verify": "done",
                "task_hr_case_review": "done",
                "task_immigration_review": "done",
                "task_visa_docs_prep": "pending",
                "task_visa_submit": "pending",
            }
        )
        prof = employee_profile_ready_for_passport_only(with_passport_scan=False, with_family=True)
        out = run_plan_view(milestones=miles, profile=prof, viewer_role="employee")
        prep = _task_by_code(out, "prepare_visa_pack")
        sub = _task_by_code(out, "submit_visa_application")
        self.assertIsNotNone(prep)
        self.assertIsNotNone(sub)
        assert prep is not None and sub is not None
        self.assertEqual(prep.status, RelocationPlanTaskStatus.BLOCKED)
        self.assertEqual(sub.status, RelocationPlanTaskStatus.BLOCKED)

    def test_family_details_completed_when_household_data_present_even_if_milestone_pending(self) -> None:
        miles = full_case_milestones({"task_profile_core": "done", "task_family_dependents": "pending"})
        prof = employee_profile_ready_for_passport_only(with_family=True)
        out = run_plan_view(milestones=miles, profile=prof, viewer_role="employee")
        fam = _task_by_code(out, "confirm_family_details")
        self.assertIsNotNone(fam)
        assert fam is not None
        self.assertEqual(fam.status, RelocationPlanTaskStatus.COMPLETED)

    def test_arrange_movers_not_applicable_when_shipment_services_not_selected(self) -> None:
        miles = full_case_milestones()
        prof = employee_profile_ready_for_passport_only(with_family=True)
        db = mock_db_with_services(selected=["housing"])
        out = run_plan_view(milestones=miles, profile=prof, viewer_role="employee", db=db)
        movers = _task_by_code(out, "arrange_movers")
        self.assertIsNotNone(movers)
        assert movers is not None
        self.assertEqual(movers.status, RelocationPlanTaskStatus.NOT_APPLICABLE)

    def test_hr_next_action_is_hr_review_when_predep_ready_for_hr_gate(self) -> None:
        miles = full_case_milestones(
            {
                "task_profile_core": "done",
                "task_family_dependents": "done",
                "task_passport_upload": "done",
                "task_employment_letter": "done",
                "task_route_verify": "done",
                "task_hr_case_review": "pending",
            }
        )
        prof = employee_profile_ready_for_passport_only(with_passport_scan=True, with_family=True)
        out = run_plan_view(milestones=miles, profile=prof, viewer_role="hr")
        self.assertIsNotNone(out.next_action)
        self.assertEqual(_next_action_task_code(out), "hr_review_case_data")

    def test_when_predep_complete_next_action_moves_to_immigration_phase(self) -> None:
        """
        Use a tight milestone slice (no logistics rows). Pre-departure is fully terminal;
        the highlighted next step is the first immigration HR task (phase may read
        ``blocked`` while downstream visa rows are still gated — that is expected UX).
        """
        miles = [
            _mt_row("task_profile_core", status="done"),
            _mt_row("task_family_dependents", status="done"),
            _mt_row("task_passport_upload", status="done"),
            _mt_row("task_employment_letter", status="done"),
            _mt_row("task_route_verify", status="done"),
            _mt_row("task_hr_case_review", status="done"),
            _mt_row("task_immigration_review", status="pending"),
            _mt_row("task_visa_docs_prep", status="pending"),
            _mt_row("task_visa_submit", status="pending"),
        ]
        prof = employee_profile_ready_for_passport_only(with_passport_scan=True, with_family=True)
        out = run_plan_view(milestones=miles, profile=prof, viewer_role="hr")
        pre = next(p for p in out.phases if p.phase_key == "pre_departure")
        self.assertEqual(pre.status.value, "completed")
        imm = next(p for p in out.phases if p.phase_key == "immigration")
        self.assertGreater(len(imm.tasks), 0)
        self.assertIsNotNone(out.next_action)
        self.assertEqual(_next_action_task_code(out), "schedule_immigration_review")

    def test_phases_are_ordered_subset_and_omit_empty_phases(self) -> None:
        """Contract: only phases that contain ≥1 milestone appear, in ``PHASE_ORDER``."""
        miles = full_case_milestones()
        out = run_plan_view(milestones=miles, profile=employee_profile_ready_for_passport_only())
        keys = _phase_keys_in_order(out)
        idx = {k: i for i, k in enumerate(PHASE_ORDER)}
        self.assertEqual(keys, sorted(keys, key=lambda k: idx.get(k, 999)))
        for pk in keys:
            self.assertIn(pk, PHASE_ORDER)
        for ph in out.phases:
            self.assertGreater(len(ph.tasks), 0)

    def test_phase_grouping_puts_core_and_passport_in_pre_departure(self) -> None:
        miles = full_case_milestones()
        out = run_plan_view(milestones=miles, profile=employee_profile_ready_for_passport_only())
        pre = next(p for p in out.phases if p.phase_key == "pre_departure")
        codes = {t.task_code for t in pre.tasks}
        self.assertIn("confirm_employee_core_profile", codes)
        self.assertIn("upload_passport_copy", codes)

    def test_task_order_in_phase_respects_dependencies_before_passport(self) -> None:
        """Topo order: core profile precedes passport upload within pre-departure."""
        miles = full_case_milestones(
            {"task_profile_core": "pending", "task_passport_upload": "pending"}
        )
        out = run_plan_view(milestones=miles, profile=employee_profile_ready_for_passport_only())
        pre = next(p for p in out.phases if p.phase_key == "pre_departure")
        codes = [t.task_code for t in pre.tasks]
        self.assertIn("confirm_employee_core_profile", codes)
        self.assertIn("upload_passport_copy", codes)
        self.assertLess(
            codes.index("confirm_employee_core_profile"),
            codes.index("upload_passport_copy"),
        )


class RelocationPlanViewContractTests(unittest.TestCase):
    def test_response_round_trips_through_pydantic_and_json(self) -> None:
        miles = full_case_milestones({"task_profile_core": "done"})
        out = run_plan_view(milestones=miles, profile=employee_profile_ready_for_passport_only())
        dumped = out.model_dump(mode="json")
        roundtrip = RelocationPlanViewResponse.model_validate(dumped)
        self.assertEqual(roundtrip.case_id, out.case_id)
        self.assertEqual(roundtrip.role, RelocationPlanViewRole.EMPLOYEE)
        self.assertTrue(json.dumps(dumped))


class RelocationPlanViewAuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._main_gate = False
        try:
            from backend.main import (  # noqa: WPS433 (runtime import)
                _relocation_plan_view_query_role,
                _require_case_id_assignment_visible,
            )

            cls._require_case_id_assignment_visible = _require_case_id_assignment_visible
            cls._relocation_plan_view_query_role = _relocation_plan_view_query_role
            cls._main_gate = True
        except ImportError:
            pass

    def setUp(self) -> None:
        if not self._main_gate:
            self.skipTest("backend.main import unavailable (install optional deps e.g. requests)")

    def _patch_main_db(self, mock: MagicMock):
        return patch("backend.main.db", mock)

    def test_employee_cannot_open_another_employees_case(self) -> None:
        mock_db = MagicMock()
        mock_db.get_assignment_by_case_id.return_value = {
            "id": "asg-1",
            "case_id": "case-1",
            "canonical_case_id": "",
            "employee_user_id": "emp-real",
            "hr_user_id": "hr-1",
        }
        mock_db.get_assignment_by_id.return_value = mock_db.get_assignment_by_case_id.return_value
        user = {"id": "emp-other", "role": UserRole.EMPLOYEE.value, "is_admin": False, "impersonation": None}
        with self._patch_main_db(mock_db):
            with self.assertRaises(Exception) as ctx:
                self._require_case_id_assignment_visible("case-1", user)
        from fastapi import HTTPException

        self.assertIsInstance(ctx.exception, HTTPException)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_hr_same_company_allowed_when_not_direct_owner(self) -> None:
        mock_db = MagicMock()
        mock_db.get_assignment_by_case_id.return_value = {
            "id": "asg-2",
            "case_id": "case-2",
            "canonical_case_id": "",
            "employee_user_id": "emp-1",
            "hr_user_id": "hr-owner",
        }
        mock_db.get_assignment_by_id.return_value = mock_db.get_assignment_by_case_id.return_value
        mock_db.get_hr_company_id.return_value = "company-a"
        mock_db.assignment_belongs_to_company.return_value = True
        user = {"id": "hr-peer", "role": UserRole.HR.value, "is_admin": False, "impersonation": None}
        with self._patch_main_db(mock_db):
            row = self._require_case_id_assignment_visible("case-2", user)
        self.assertEqual(row["id"], "asg-2")

    def test_hr_other_company_denied(self) -> None:
        mock_db = MagicMock()
        mock_db.get_assignment_by_case_id.return_value = {
            "id": "asg-3",
            "case_id": "case-3",
            "canonical_case_id": "",
            "employee_user_id": "emp-1",
            "hr_user_id": "hr-owner",
        }
        mock_db.get_assignment_by_id.return_value = mock_db.get_assignment_by_case_id.return_value
        mock_db.get_hr_company_id.return_value = "company-intruder"
        mock_db.assignment_belongs_to_company.return_value = False
        user = {"id": "hr-intruder", "role": UserRole.HR.value, "is_admin": False, "impersonation": None}
        with self._patch_main_db(mock_db):
            from fastapi import HTTPException

            with self.assertRaises(HTTPException) as ctx:
                self._require_case_id_assignment_visible("case-3", user)
        self.assertEqual(ctx.exception.status_code, 403)


class RelocationPlanViewQueryRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._main_gate = False
        try:
            from backend.main import _relocation_plan_view_query_role  # noqa: WPS433

            cls._relocation_plan_view_query_role = _relocation_plan_view_query_role
            cls._main_gate = True
        except ImportError:
            pass

    def setUp(self) -> None:
        if not self._main_gate:
            self.skipTest("backend.main import unavailable (install optional deps e.g. requests)")

    def test_default_role_follows_principal(self) -> None:
        hr_user = {"id": "h1", "role": UserRole.HR.value, "is_admin": False, "impersonation": None}
        emp_user = {"id": "e1", "role": UserRole.EMPLOYEE.value, "is_admin": False, "impersonation": None}
        self.assertEqual(self._relocation_plan_view_query_role(hr_user, None), "hr")
        self.assertEqual(self._relocation_plan_view_query_role(emp_user, None), "employee")

    def test_employee_cannot_request_hr_lens(self) -> None:
        from fastapi import HTTPException

        emp_user = {"id": "e1", "role": UserRole.EMPLOYEE.value, "is_admin": False, "impersonation": None}
        with self.assertRaises(HTTPException) as ctx:
            self._relocation_plan_view_query_role(emp_user, "hr")
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
