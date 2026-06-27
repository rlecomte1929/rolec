"""Regression: list and detail read models must agree on case status.

`GET /api/employee/cases` (list) reports `normalize_status(assignment.status)`;
`GET /api/cases/{id}` (detail) reports `wizard_cases.status` raw. Before the fix,
submit advanced only the assignment, so post-submit the list said `submitted`
while the detail still said `created`. `submit_assignment` now also advances
`wizard_cases.status`.

A full end-to-end submit needs profile ≥90% + a background executor, so these
tests guard the two things that actually keep the read models in parity:
(1) the value submit writes equals what the list endpoint normalizes to, and
(2) the handler performs the sync, after the assignment flips.
"""

from __future__ import annotations

import os

from backend.main import normalize_status
from backend.schemas import AssignmentStatus


def _submit_assignment_source() -> str:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backend", "main.py"
    )
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    start = src.index("def submit_assignment(")
    end = src.index("\n@app.", start + 1)
    return src[start:end]


def test_written_status_matches_list_normalization():
    """The value submit writes to wizard_cases.status (the detail read model) must
    equal what the list endpoint reports for a submitted assignment — else the two
    surfaces diverge again."""
    written = AssignmentStatus.SUBMITTED.value          # detail: wizard_cases.status
    listed = normalize_status(AssignmentStatus.SUBMITTED.value)  # list: normalize_status(assignment.status)
    assert written == listed == "submitted"


def test_submit_advances_wizard_case_status_after_assignment_flip():
    src = _submit_assignment_source()
    assert "set_assignment_submitted" in src
    assert "wc.status = AssignmentStatus.SUBMITTED.value" in src
    # The wizard-case sync must run AFTER the assignment is marked submitted.
    assert src.index("set_assignment_submitted") < src.index(
        "wc.status = AssignmentStatus.SUBMITTED.value"
    )
    # And it must be best-effort so it can never fail the submit.
    sync_idx = src.index("wc.status = AssignmentStatus.SUBMITTED.value")
    assert "try:" in src[:sync_idx]


def test_submit_advances_intake_step_to_total():
    # A submitted case must store completed intake progress (intake_step ==
    # intake_total_steps) so the dashboard widget doesn't show "Step 1 of 5".
    # The client's updateIntakeProgress is fire-and-forget, so the submit handler
    # advances it server-side, after the assignment flip, best-effort.
    src = _submit_assignment_source()
    assert "update_assignment_intake_progress" in src
    progress_idx = src.index("update_assignment_intake_progress")
    assert src.index("set_assignment_submitted") < progress_idx
    assert "step=_total" in src and "total_steps=_total" in src
    assert "try:" in src[:progress_idx]  # best-effort, never fails the submit


def test_submit_reads_assignment_intake_draft_authoritatively():
    """AIQ-1311: submit must validate from the reliable assignment autosave draft
    (case_assignments.intake_draft, snake_case), converted to the canonical
    camelCase shape — not solely the frontend-patched wizard_cases row, which used
    a divergent case-id and left submit reading an empty draft (400 on a
    fully-filled wizard)."""
    src = _submit_assignment_source()
    assert "get_assignment_intake" in src
    assert "intake_draft_to_case_draft" in src
    # The conversion must happen BEFORE the completeness check that drives the 400.
    assert src.index("intake_draft_to_case_draft") < src.index("missing_intake_basics(submit_draft)")


def test_submit_prefers_assignment_draft_over_wizard_cases_fallback():
    """The wizard_cases draft is only a back-compat fallback; the assignment draft
    is read first."""
    src = _submit_assignment_source()
    # Assignment draft is read before the wizard_cases fallback lookup.
    assert src.index("get_assignment_intake") < src.index("app_crud.get_case(session, assignment_id)")


def test_submit_syncs_relocation_case_from_authoritative_draft():
    """HR reads relocation_cases; the route sync must use the authoritative
    assignment-derived draft so HR sees origin/destination after submit (A-12)."""
    src = _submit_assignment_source()
    assert "sync_relocation_case_route_from_wizard_draft" in src
    sync_idx = src.index("sync_relocation_case_route_from_wizard_draft")
    # The authoritative draft is substituted before the sync call.
    assert "draft = submit_draft" in src[:sync_idx]
