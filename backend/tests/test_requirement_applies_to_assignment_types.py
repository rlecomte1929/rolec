"""AIQ-1349 follow-up — data-driven requirement applicability by assignment type.

A requirement_items row may declare appliesToAssignmentTypes (JSON array, surfaced
into the rule dict by requirements_builder). apply_rules drops requirements that
don't apply to the case's assignment_type; None/empty applies to all; legacy cases
with no assignment_type keep everything.
"""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.app.services.rules_engine import apply_rules, _applies_to_assignment_type


def _base():
    return [
        {"id": "all", "title": "Universal ID check", "pillar": "IDENTITY"},  # no applies → all
        {"id": "lt", "title": "Permanent residence registration", "pillar": "RESIDENCE",
         "appliesToAssignmentTypes": ["LTA", "PERMANENT"]},
    ]


def _draft(assignment_type=None):
    d = {"relocationBasics": {"purpose": "employment"}, "familyMembers": {}, "employeeProfile": {},
         "assignmentContext": {}}
    if assignment_type:
        d["assignmentContext"]["assignmentType"] = assignment_type
    return d


def _ids(expanded):
    return {r.get("id") for r in expanded}


def test_helper_semantics():
    assert _applies_to_assignment_type({}, "STA") is True  # no field → all
    assert _applies_to_assignment_type({"appliesToAssignmentTypes": []}, "STA") is True
    assert _applies_to_assignment_type({"appliesToAssignmentTypes": ["LTA"]}, "STA") is False
    assert _applies_to_assignment_type({"appliesToAssignmentTypes": ["lta", "sta"]}, "STA") is True


def test_sta_drops_long_term_only_requirement():
    _rf, expanded, flags = apply_rules(_draft("STA"), _base())
    ids = _ids(expanded)
    assert "all" in ids                      # universal kept
    assert "lt" not in ids                   # LTA/PERMANENT-only dropped for STA
    assert "Permanent residence registration" in flags.get("staWaived", [])


def test_lta_keeps_long_term_only_requirement():
    _rf, expanded, _flags = apply_rules(_draft("LTA"), _base())
    assert {"all", "lt"} <= _ids(expanded)


def test_legacy_case_without_assignment_type_keeps_all():
    _rf, expanded, _flags = apply_rules(_draft(None), _base())
    assert {"all", "lt"} <= _ids(expanded)
