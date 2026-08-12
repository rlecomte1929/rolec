"""An assignment id must return the same requirements as the canonical case id.

Found by walking the live product on 2026-08-12. The employee dossier for a real FR→NO
case rendered:

    "Requirements not available yet for UNKNOWN"

on a case whose `dest_country` is plainly `NO`. The same case, addressed by its CANONICAL
id, returned all 22 Norway requirements. Two ids, one case, opposite answers.

`requirements_builder` keys on the canonical case id, but the handler passed the raw route
param straight through — and route params are routinely assignment ids:
`HrDashboard.tsx` navigates with `assignment.id`. So the HR case dossier (which renders the
same component) would have shown a coverage gap on every case reached from the dashboard.

It failed SAFE — the honest "we can't confirm the requirements, not that there are none"
notice, never "nothing is required of you" — which is exactly why nobody caught it. It
looked like a catalog gap.

TWO HANDLERS, AND ONLY ONE RUNS. `backend/routes/compat.py`, `cases_read.py` and
`cases.py` all declare `GET /api/cases/{case_id}/requirements`. FastAPI matches the
FIRST registered, which is compat. `test_the_serving_handler_is_the_one_we_fixed` pins
that, because fixing only the modular copies would have shipped a no-op.
"""
from __future__ import annotations

import os
import sys
from unittest import mock

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest  # noqa: E402

CANONICAL = "a839d6f4-dc82-4e68-9eaf-f893c3206c27"
ASSIGNMENT = "ec13fc07-47a8-4179-8958-f286e950c890"


def test_the_serving_handler_is_the_one_we_fixed():
    """FastAPI matches the first registered route. If this order ever changes, the fix
    silently moves to a handler nobody calls — so assert the winner by name."""
    from backend.main import app

    handlers = [
        r.endpoint.__module__
        for r in app.routes
        if getattr(r, "path", "") == "/api/cases/{case_id}/requirements"
        and getattr(r, "endpoint", None) is not None
    ]
    assert handlers, "the requirements route disappeared"
    assert handlers[0] == "backend.routes.compat", (
        f"the first-match handler is now {handlers[0]!r}; the resolved-id fix must live "
        "there, not only in the shadowed copies"
    )


def test_compat_resolves_an_assignment_id_before_computing():
    """The live handler must hand `compute_case_requirements` the CANONICAL id."""
    from backend.routes import compat

    seen = {}

    def _fake_compute(case_id):
        seen["case_id"] = case_id
        raise ValueError("stop here — we only care which id was passed")

    with mock.patch.object(compat, "resolve_case_forms_case_id", return_value=CANONICAL) as resolver, \
         mock.patch.object(compat, "compute_case_requirements", side_effect=_fake_compute), \
         mock.patch.object(compat, "_extract_bearer_token", return_value="session-token"), \
         mock.patch.object(compat, "_is_jwt", return_value=False), \
         mock.patch.object(compat, "_get_user_from_session_token", return_value={"id": "u1"}), \
         mock.patch.object(compat, "_get_case_row_for_user", return_value=None), \
         mock.patch.object(compat, "_ensure_wizard_case", return_value=None):
        with pytest.raises(ValueError):
            compat.compat_get_requirements(ASSIGNMENT, authorization="Bearer session-token")

    resolver.assert_called_once_with(ASSIGNMENT)
    assert seen["case_id"] == CANONICAL, (
        "the raw route param reached the requirements builder — an assignment id there "
        'resolves the destination to "UNKNOWN"'
    )


def test_a_canonical_id_is_passed_through_unchanged():
    """`resolve_case_forms_case_id` returns its input when nothing resolves, so the
    canonical path must be untouched by the fix."""
    from backend.routes import compat

    seen = {}

    def _fake_compute(case_id):
        seen["case_id"] = case_id
        raise ValueError("stop")

    with mock.patch.object(compat, "resolve_case_forms_case_id", side_effect=lambda x: x), \
         mock.patch.object(compat, "compute_case_requirements", side_effect=_fake_compute), \
         mock.patch.object(compat, "_extract_bearer_token", return_value="session-token"), \
         mock.patch.object(compat, "_is_jwt", return_value=False), \
         mock.patch.object(compat, "_get_user_from_session_token", return_value={"id": "u1"}), \
         mock.patch.object(compat, "_get_case_row_for_user", return_value=None), \
         mock.patch.object(compat, "_ensure_wizard_case", return_value=None):
        with pytest.raises(ValueError):
            compat.compat_get_requirements(CANONICAL, authorization="Bearer session-token")

    assert seen["case_id"] == CANONICAL


def test_modular_handlers_key_on_the_resolved_id_too():
    """The shadowed copies must not carry the bug forward into the modular cutover."""
    from backend.app.routers import cases as cases_router
    from backend.app.routers import cases_read

    for module in (cases_read, cases_router):
        seen = {}

        def _fake_compute(case_id, _seen=seen):
            _seen["case_id"] = case_id
            raise ValueError("stop")

        with mock.patch.object(module, "_assert_case_access", return_value=CANONICAL) as guard, \
             mock.patch.object(module, "compute_case_requirements", side_effect=_fake_compute):
            with pytest.raises(Exception):
                module.get_case_requirements(ASSIGNMENT, user={"id": "u1"})

        guard.assert_called_once_with({"id": "u1"}, ASSIGNMENT)
        assert seen["case_id"] == CANONICAL, (
            f"{module.__name__} still passes the raw route param"
        )
