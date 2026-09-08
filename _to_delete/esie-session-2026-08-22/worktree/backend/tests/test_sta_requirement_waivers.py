"""AIQ-1349 Phase 2 — short-term assignments (STA) get a lighter requirement set.

apply_rules is the live requirements engine's rule stage (compute_case_requirements
-> GET /{case_id}/requirements). For STA we suppress the two duration-driven,
family-settling DEPENDENTS requirements (local school enrolment + dependent work
authorization) that only apply to a lasting move. LTA/PERMANENT keep the full set.
Identity requirements are never waived.
"""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.app.services.rules_engine import apply_rules


def _draft(assignment_type: str):
    return {
        "relocationBasics": {"purpose": "employment", "hasDependents": True,
                             "targetMoveDate": "2026-09-01"},
        "employeeProfile": {"passportExpiry": "2030-01-01"},
        "familyMembers": {
            "spouse": {"fullName": "Partner", "wantsToWork": True},
            "children": [{"dateOfBirth": "2016-04-01"}],  # school age
        },
        "assignmentContext": {"assignmentType": assignment_type},
    }


def _titles(expanded):
    return {r.get("title") for r in expanded}


def test_lta_keeps_full_dependent_requirements():
    _rf, expanded, flags = apply_rules(_draft("LTA"), [])
    titles = _titles(expanded)
    assert "School enrollment documents" in titles
    assert "Dependent work authorization rules" in titles
    assert "staWaived" not in flags


def test_sta_waives_school_and_dependent_work():
    _rf, expanded, flags = apply_rules(_draft("STA"), [])
    titles = _titles(expanded)
    assert "School enrollment documents" not in titles
    assert "Dependent work authorization rules" not in titles
    # transparency: the engine records what it waived
    assert set(flags.get("staWaived", [])) == {
        "School enrollment documents",
        "Dependent work authorization rules",
    }


def test_sta_still_emits_identity_requirements():
    # passport expiry <= move date must still flag for STA (not a long-term concern).
    draft = _draft("STA")
    draft["employeeProfile"]["passportExpiry"] = "2026-01-01"  # before the move
    _rf, expanded, _flags = apply_rules(draft, [])
    titles = _titles(expanded)
    assert any("Passport expiry" in t for t in titles)
