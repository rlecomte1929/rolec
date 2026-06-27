"""AIQ-1311 · Guard that submit_assignment is backend-authoritative.

A full end-to-end submit needs a DB + profile ≥90% + a background executor, so —
mirroring test_submit_status_parity — this guards the wiring via source
introspection: submit must read case_assignments.intake_draft, convert it
snake→camel, and prefer that authoritative draft over wizard_cases.draft_json for
both the completeness validation and the relocation_cases promotion.
"""
from __future__ import annotations

import os


def _submit_assignment_source() -> str:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backend", "main.py"
    )
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    start = src.index("def submit_assignment(")
    end = src.index("\n@app.", start + 1)
    return src[start:end]


def test_submit_reads_assignment_intake_draft_and_converts():
    src = _submit_assignment_source()
    # Reads the reliable assignment draft (keyed by assignment_id) ...
    assert "get_assignment_intake(" in src
    # ... and converts snake→camel via the new backend twin.
    assert "intake_draft_to_case_draft(" in src
    assert "authoritative_draft" in src


def test_authoritative_draft_preferred_before_wizard_cases_lookup():
    src = _submit_assignment_source()
    # The authoritative (assignment) draft must be computed before the legacy
    # wizard_cases.draft_json fallback path runs.
    assert src.index("authoritative_draft") < src.index("case.draft_json")
    # And the promotion prefers it too.
    assert "if authoritative_draft is not None:" in src


def test_completeness_gate_still_present_and_pre_status_flip():
    """The 400 guard must still exist and run before the assignment flips to
    submitted — we changed the draft SOURCE, not the guard."""
    src = _submit_assignment_source()
    assert "missing_intake_basics(" in src
    assert "incomplete_intake_detail(" in src
    # Use the call form — "set_assignment_submitted" also appears in an earlier comment.
    assert src.index("incomplete_intake_detail(") < src.index("set_assignment_submitted(assignment_id)")


def test_existing_status_parity_markers_preserved():
    """Don't regress the test_submit_status_parity invariants while restructuring."""
    src = _submit_assignment_source()
    assert "set_assignment_submitted" in src
    assert "wc.status = AssignmentStatus.SUBMITTED.value" in src
    assert "update_assignment_intake_progress" in src
    assert src.index("set_assignment_submitted") < src.index(
        "wc.status = AssignmentStatus.SUBMITTED.value"
    )
