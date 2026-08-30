"""The roadmap must not show visa/permit steps to a free mover.

Measured on the base-case clone 2026-08-30: a Spanish (EU/EEA) national moving to Dublin was
shown "Prepare visa pack", "Submit visa application" and "Book biometrics" — steps a free mover
never takes. The requirements engine already suppressed them; the roadmap did not. These tests
pin the gate, and pin that it FAILS OPEN — an unknown nationality hides no step.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from backend.app.services.relocation_plan_view_service import _filter_milestones_for_nationality
from backend.relocation_plan_task_library import FREE_MOVER_WAIVED_MILESTONE_TYPES

_MILESTONES = [
    {"milestone_type": "task_profile_core"},
    {"milestone_type": "task_visa_docs_prep"},
    {"milestone_type": "task_visa_submit"},
    {"milestone_type": "task_biometrics"},
    {"milestone_type": "task_temp_housing"},
    {"milestone_type": "task_tax_local_registration"},
]


def _types(rows):
    return {r["milestone_type"] for r in rows}


def test_free_mover_loses_the_visa_and_permit_steps():
    prof = {"employeeProfile": {"nationality": "ES"}, "relocationBasics": {"destCountry": "IE"}}
    out = _filter_milestones_for_nationality(_MILESTONES, prof)
    assert _types(out).isdisjoint(FREE_MOVER_WAIVED_MILESTONE_TYPES)
    # Non-visa steps survive untouched.
    assert {"task_profile_core", "task_temp_housing", "task_tax_local_registration"} <= _types(out)


def test_own_national_returning_home_also_loses_them():
    prof = {"employeeProfile": {"nationality": "IE"}, "relocationBasics": {"destCountry": "IE"}}
    assert _types(_filter_milestones_for_nationality(_MILESTONES, prof)).isdisjoint(
        FREE_MOVER_WAIVED_MILESTONE_TYPES)


def test_third_country_keeps_the_visa_track():
    prof = {"employeeProfile": {"nationality": "VE"}, "relocationBasics": {"destCountry": "IE"}}
    out = _filter_milestones_for_nationality(_MILESTONES, prof)
    assert FREE_MOVER_WAIVED_MILESTONE_TYPES <= _types(out)


def test_unknown_nationality_fails_open_and_hides_nothing():
    for prof in ({}, {"employeeProfile": {}}, {"relocationBasics": {"destCountry": "IE"}}):
        out = _filter_milestones_for_nationality(_MILESTONES, prof)
        assert len(out) == len(_MILESTONES), prof


def test_us_bound_eu_passport_is_not_a_free_mover():
    # An EU passport buys nothing at the US border — classify returns THIRD_COUNTRY, visa kept.
    prof = {"employeeProfile": {"nationality": "ES"}, "relocationBasics": {"destCountry": "US"}}
    out = _filter_milestones_for_nationality(_MILESTONES, prof)
    assert FREE_MOVER_WAIVED_MILESTONE_TYPES <= _types(out)
