"""Regression test for HR dashboard / case-detail corridor parity.

The HR dashboard list (GET /api/hr/assignments) used to read
relocation_cases.home_country / host_country directly, while the case-detail
view applied a precedence (employee_profiles.movePlan ->
relocation_cases.profile_json.relocationBasics -> stored home/host_country).
The list now mirrors that precedence via _resolve_assignment_route_for_list.
"""
from __future__ import annotations

import json

from backend.main import _resolve_assignment_route_for_list


def test_falls_back_to_stored_columns_when_no_profile_json():
    case_row = {"home_country": "France", "host_country": "Germany", "profile_json": None}
    origin, dest = _resolve_assignment_route_for_list(
        case_row=case_row, employee_profile_json=None
    )
    assert origin == "France"
    assert dest == "Germany"


def test_relocation_basics_overrides_stored_columns():
    case_row = {
        "home_country": "France",
        "host_country": "Germany",
        "profile_json": json.dumps(
            {"relocationBasics": {"originCountry": "Norway", "destCountry": "Singapore"}}
        ),
    }
    origin, dest = _resolve_assignment_route_for_list(
        case_row=case_row, employee_profile_json=None
    )
    assert origin == "Norway"
    assert dest == "Singapore"


def test_employee_profile_move_plan_has_highest_precedence():
    case_row = {
        "home_country": "France",
        "host_country": "Germany",
        "profile_json": json.dumps(
            {"relocationBasics": {"originCountry": "Norway", "destCountry": "Singapore"}}
        ),
    }
    employee_profile = {
        "movePlan": {"origin": "Oslo, Norway", "destination": "Singapore"}
    }
    origin, dest = _resolve_assignment_route_for_list(
        case_row=case_row, employee_profile_json=employee_profile
    )
    assert origin == "Oslo, Norway"
    assert dest == "Singapore"


def test_blank_profile_values_do_not_clobber_stored_columns():
    case_row = {
        "home_country": "France",
        "host_country": "Germany",
        "profile_json": json.dumps(
            {"relocationBasics": {"originCountry": "  ", "destCountry": ""}}
        ),
    }
    employee_profile = {"movePlan": {"origin": "", "destination": "   "}}
    origin, dest = _resolve_assignment_route_for_list(
        case_row=case_row, employee_profile_json=employee_profile
    )
    assert origin == "France"
    assert dest == "Germany"


def test_handles_dict_profile_json_not_just_string():
    case_row = {
        "home_country": "France",
        "host_country": "Germany",
        "profile_json": {"relocationBasics": {"originCountry": "Norway", "destCountry": "Singapore"}},
    }
    origin, dest = _resolve_assignment_route_for_list(
        case_row=case_row, employee_profile_json=None
    )
    assert origin == "Norway"
    assert dest == "Singapore"
