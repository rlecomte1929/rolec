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


def _read(*parts: str) -> str:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), *parts)
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def test_both_endpoints_use_the_shared_resolver():
    """Single source of truth: BOTH the case list (get_employee_cases) and the LIVE
    detail handler (routes/compat.py compat_get_case → _get_wizard_case_dto) must
    derive status from db.resolve_case_status, so they can never disagree. The
    shadowed cases_read.get_case is aligned too. (compat is the LIVE handler — see
    reference_compat_handler_shadows_cases_read; guarding only cases_read is why
    #851 was a no-op.)"""
    # LIST
    main_src = _read("main.py")
    list_body = main_src[main_src.index("def get_employee_cases("):]
    list_body = list_body[: list_body.index("\n@app.")]
    assert "db.resolve_case_status(case_id, effective[\"id\"]" in list_body

    # DETAIL — live (compat) and shadowed (cases_read), both via the resolver,
    # both passing it into _case_dto.
    compat_src = _read("routes", "compat.py")
    wiz = compat_src[compat_src.index("def _get_wizard_case_dto("):]
    wiz = wiz[: wiz.index("\ndef ", 1)]
    assert "db.resolve_case_status(case_id, employee_user_id)" in wiz
    assert "assignment_status=assignment_status" in wiz

    cr_src = _read("app", "routers", "cases_read.py")
    gc = cr_src[cr_src.index("def get_case("):]
    gc = gc[: gc.index("\n@router.", 1)]
    assert "resolve_case_status(case_id, employee_user_id)" in gc
    assert "assignment_status=assignment_status" in gc
