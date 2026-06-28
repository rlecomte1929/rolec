"""AIQ-1349 PR1 — the assignment-type extractor that feeds the canonical-case
bridge (public.cases.assignment_type / expected_duration_months)."""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.app.routers.cases_write import _assignment_derived


def test_normalizes_assignment_type_to_upper():
    assert _assignment_derived({"assignmentContext": {"assignmentType": "sta"}})["assignment_type"] == "STA"
    assert _assignment_derived({"assignmentContext": {"assignmentType": " lta "}})["assignment_type"] == "LTA"
    assert _assignment_derived({"assignmentContext": {"assignmentType": "PERMANENT"}})["assignment_type"] == "PERMANENT"


def test_coerces_duration_to_int():
    assert _assignment_derived({"assignmentContext": {"expectedDurationMonths": "6"}})["expected_duration_months"] == 6
    assert _assignment_derived({"assignmentContext": {"expectedDurationMonths": 18}})["expected_duration_months"] == 18
    # junk / empty → None, never a crash
    assert _assignment_derived({"assignmentContext": {"expectedDurationMonths": "soon"}})["expected_duration_months"] is None


def test_absent_yields_none_so_deep_merge_never_clobbers():
    empty = _assignment_derived({})
    assert empty == {"assignment_type": None, "expected_duration_months": None}
    blank = _assignment_derived({"assignmentContext": {"assignmentType": "  "}})
    assert blank["assignment_type"] is None
