"""HR validates the roadmap; the employee then acknowledges it.

Today the EMPLOYEE self-validates and HR only gets a notification afterwards. The
intended order is:

    intake -> roadmap generated -> HR approves -> employee acknowledges -> tasks start

The store already existed (`roadmap_review_status`: released_to_user,
regeneration_requested, reviewer_id, notes) — it was admin-only, written by the
specialist-review surface. This exposes it to HR.

THE DEFAULT IS THE DANGEROUS PART. 47 production cases already had a roadmap and NONE
had a review row. "No row = not released" would have hidden the plan from every one of
them the day this shipped. So an absent row means RELEASED, and a newly generated
roadmap explicitly writes an unreleased row. These tests pin both halves — get either
wrong and either every existing employee loses their plan, or the gate never engages.
"""
from __future__ import annotations

import os

import pytest

# Mounting the prod app trips the query counter against the mocked engine — the repo's
# other app-mounted tests set this the same way.
os.environ["RELOPASS_QUERY_COUNTER_OFF"] = "1"

from backend.app.routers.hr_roadmap_review import RoadmapReviewDTO, _to_dto


class _Row:
    def __init__(self, released=False, regen=False, reviewer="hr-1", notes=None):
        self.released_to_user = released
        self.regeneration_requested = regen
        self.reviewer_id = reviewer
        self.notes = notes


class TestAnAbsentDecisionMeansReleased:
    """The employee never loses a roadmap they already had."""

    def test_no_review_row_is_released(self):
        dto = _to_dto("c1", None)
        assert dto.released_to_user is True
        assert dto.reviewed is False, "we must be able to tell 'nobody looked' from 'HR approved'"

    def test_the_default_on_the_dto_is_released(self):
        assert RoadmapReviewDTO(case_id="c1").released_to_user is True

    def test_the_plan_view_falls_open_when_the_lookup_dies(self):
        """A gate's own query failing must not hide someone's relocation plan.

        NOTE: `session_factory` is a PARAMETER of the plan-view builder, not a module
        global. My first cut of _resolve_roadmap_release referenced it as a global —
        inside a try/except, so the NameError would have been swallowed, the gate would
        have silently never engaged, and every roadmap would have looked released. This
        test is what surfaced it."""
        from backend.app.services import relocation_plan_view_service as svc

        def boom():
            raise RuntimeError("db down")

        released, notes = svc._resolve_roadmap_release(boom, "c1")
        assert released is True
        assert notes is None

    def test_the_release_is_actually_read_when_the_row_exists(self):
        """The other half: the gate must ACTUALLY engage, not just fail open."""
        from contextlib import contextmanager

        from backend.app.services import relocation_plan_view_service as svc

        class _Session:
            def get(self, _model, _cid):
                return _Row(released=False, regen=True, notes="Budget wrong.")

        @contextmanager
        def factory():
            yield _Session()

        released, notes = svc._resolve_roadmap_release(factory, "c1")
        assert released is False, "an unreleased roadmap must actually be held back"
        assert notes == "Budget wrong."


class TestHrDecisionsAreDistinguishable:
    def test_approved(self):
        dto = _to_dto("c1", _Row(released=True))
        assert dto.released_to_user is True
        assert dto.reviewed is True
        assert dto.regeneration_requested is False

    def test_sent_back_for_changes(self):
        dto = _to_dto("c1", _Row(released=False, regen=True, notes="Housing budget is wrong."))
        assert dto.released_to_user is False
        assert dto.regeneration_requested is True
        assert dto.notes == "Housing budget is wrong."
        # The employee is shown "HR is reviewing", never a plan HR has rejected — and
        # never an empty screen.


class TestARejectionMustCarryAReason:
    def test_request_changes_with_no_notes_is_rejected(self):
        """A rejection with no reason is indistinguishable from a bug, and leaves the
        employee waiting on something nobody can act on."""
        from fastapi import HTTPException

        from backend.app.routers.hr_roadmap_review import RequestChangesBody, request_changes

        with pytest.raises(HTTPException) as exc:
            request_changes("c1", RequestChangesBody(notes="   "), hr_user={"id": "hr-1"})
        assert exc.value.status_code == 422


class TestTheRouteIsRegisteredWhereProdActuallyBoots:
    """Render runs `uvicorn backend.main:app`. A router registered only in the modular
    app 405s in production — this repo has been bitten three times (AI-002 v2 hotfix,
    AIQ-567, AIQ-568)."""

    def test_the_prod_app_exposes_the_routes(self):
        from backend.main import app

        paths = {r.path for r in app.routes}
        for expected in (
            "/api/hr/cases/{case_id}/roadmap-review",
            "/api/hr/cases/{case_id}/roadmap-review/approve",
            "/api/hr/cases/{case_id}/roadmap-review/request-changes",
        ):
            assert expected in paths, f"{expected} would 405 in production"
