"""Regression: case list and detail endpoints report identical status (WI3).

`GET /api/employee/cases` (list) reports `normalize_status(case_assignments.status)`.
`GET /api/cases/{id}` (detail) used to report `wizard_cases.status`, which only ever
held 'created' until submit — so the two diverged for every pre-submit state.

Both endpoints now derive status from the SAME source (the assignment) via the SAME
shared `normalize_status`, so they agree by construction for any lifecycle value,
regardless of `wizard_cases.status`. These tests lock that in (parity by construction)
plus a wiring guard that the detail handler resolves the assignment and passes it.
"""

from __future__ import annotations

import os
from datetime import datetime
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite://")

from backend.app.services.case_service import _case_dto  # noqa: E402
from backend.app.services.case_status import normalize_status  # noqa: E402


def _fake_case(status: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="c1",
        status=status,  # wizard_cases.status — should be IGNORED when an assignment exists
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
        origin_country=None,
        origin_city=None,
        dest_country=None,
        dest_city=None,
        purpose=None,
        target_move_date=None,
        flags_json="{}",
        requirements_snapshot_id=None,
    )


def test_detail_matches_list_for_every_lifecycle_status():
    # wizard_cases.status is pinned to 'created' (its real-world value pre-submit);
    # the detail must still match what the list reports for the assignment.
    for raw in [
        "assigned", "awaiting_intake", "submitted", "approved", "rejected", "closed",
        "DRAFT", "HR_APPROVED", "EMPLOYEE_SUBMITTED",  # legacy values both must fold identically
    ]:
        list_value = normalize_status(raw)  # GET /api/employee/cases
        dto = _case_dto(_fake_case("created"), {}, assignment_status=normalize_status(raw))
        assert dto.status == list_value, f"divergence for {raw!r}: {dto.status} != {list_value}"


def test_detail_falls_back_to_case_status_without_assignment():
    dto = _case_dto(_fake_case("created"), {}, assignment_status=None)
    assert dto.status == "created"


def test_get_case_resolves_assignment_status():
    """Wiring guard: the detail handler must query case_assignments and pass the
    normalized assignment status into _case_dto."""
    path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "app", "routers", "cases_read.py"
    )
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    start = src.index("def get_case(")
    body = src[start: src.index("\n@router.", start + 1)]
    assert "FROM case_assignments" in body
    assert "normalize_status(" in body
    assert "assignment_status=assignment_status" in body


def test_compat_handler_resolves_assignment_status():
    """The LIVE GET /api/cases/{id} handler is backend.routes.compat.compat_get_case
    (registered before cases_read, so it WINS). Its _get_wizard_case_dto must also
    pass the assignment status into _case_dto — otherwise the detail endpoint falls
    back to wizard_cases.status and diverges from the list (the prod bug found
    2026-06-25 after #851 shipped to the shadowed handler)."""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "routes", "compat.py")
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    start = src.index("def _get_wizard_case_dto(")
    body = src[start: src.index("\ndef ", start + 1)]
    assert "assignment_status=assignment_status" in body
    assert "_resolve_assignment_status" in body
    assert "FROM case_assignments" in src
    assert "normalize_status(" in src
