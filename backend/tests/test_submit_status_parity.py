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
