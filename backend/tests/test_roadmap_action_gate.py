"""[AIQ-1526] The employee READS a pending roadmap; they cannot ACT on it.

The first cut of this gate (#1465) hid the whole roadmap behind "Your HR team is reviewing
your plan". That was too blunt: exploring the plan is reassuring and costs nothing. What
actually needs holding back is ACTION — HR can still send the plan back for regeneration,
and progress recorded against a plan that's about to be replaced is wasted work.

So: reads open, writes gated. And the gate has to live on the SERVER — a greyed-out button
is cosmetic, the employee can still call the API.

The fail-open direction is the dangerous one, and it runs the opposite way to the read gate:
here, guessing "pending" LOCKS someone out of their own tasks. 47 live cases have a roadmap
and no review row. So an absent row means NOT pending.
"""
from __future__ import annotations

import os

import pytest

os.environ["RELOPASS_QUERY_COUNTER_OFF"] = "1"

from fastapi import HTTPException

from backend.app.routers import hr_roadmap_review as gate


class _Row:
    def __init__(self, released: bool):
        self.released_to_user = released


def _stub_session(monkeypatch, row):
    class _Session:
        def get(self, _model, _cid):
            return row

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(gate, "SessionLocal", lambda: _Session())


class TestAnAbsentReviewRowNeverLocksAnyoneOut:
    """Fail-open. 47 live cases have a roadmap and no review row — if a missing row read as
    'pending', every one of those employees would be locked out of their own tasks."""

    def test_no_row_is_not_pending(self, monkeypatch):
        _stub_session(monkeypatch, None)
        assert gate.is_roadmap_pending_review("c1") is False
        gate.assert_roadmap_released("c1")  # must not raise

    def test_a_lookup_failure_is_not_pending(self, monkeypatch):
        def boom():
            raise RuntimeError("db down")

        monkeypatch.setattr(gate, "SessionLocal", boom)
        assert gate.is_roadmap_pending_review("c1") is False
        gate.assert_roadmap_released("c1")  # a broken gate must not block the employee


class TestTheGateActuallyEngages:
    """The other half — failing open is the right default, but the gate must still bite."""

    def test_an_unreleased_roadmap_blocks_the_action(self, monkeypatch):
        _stub_session(monkeypatch, _Row(released=False))

        assert gate.is_roadmap_pending_review("c1") is True
        with pytest.raises(HTTPException) as exc:
            gate.assert_roadmap_released("c1")

        # 409, not 403: the employee is entitled to act — just not yet. A permissions
        # error would be a lie about why.
        assert exc.value.status_code == 409
        assert "explore" in str(exc.value.detail), "tell them they can still READ the plan"

    def test_an_approved_roadmap_allows_the_action(self, monkeypatch):
        _stub_session(monkeypatch, _Row(released=True))

        assert gate.is_roadmap_pending_review("c1") is False
        gate.assert_roadmap_released("c1")  # must not raise


class TestTheGateIsWiredToTheWritePathsAndNotTheReads:
    """A gate nobody calls is decoration. These pin the actual call sites."""

    def test_validate_roadmap_is_gated(self):
        import inspect

        from backend.app.routers import cases_write

        src = inspect.getsource(cases_write.validate_roadmap)
        assert "assert_roadmap_released" in src, (
            "starting tasks on a plan HR may still replace must be blocked"
        )

    def test_the_employee_milestone_patch_is_gated_but_hr_is_not(self):
        import inspect

        from backend import main

        src = inspect.getsource(main.update_case_milestone)
        assert "assert_roadmap_released" in src
        assert "EMPLOYEE" in src, (
            "HR must NOT be gated — curating the timeline is what they are reviewing it to do"
        )

    def test_the_plan_view_read_is_NOT_gated(self):
        """Reads stay open. This is the whole point of the change."""
        import inspect

        from backend import main

        src = inspect.getsource(main.get_relocation_plan_view)
        assert "assert_roadmap_released" not in src, (
            "the employee must always be able to EXPLORE their roadmap"
        )


class TestTheMetricsEndpointIsRegisteredWhereProdBoots:
    """Render runs `uvicorn backend.main:app`. A router registered only in the modular app
    405s in production — this repo has been bitten three times."""

    def test_prod_app_exposes_the_metrics_and_notify_routes(self):
        from backend.main import app

        paths = {r.path for r in app.routes}
        for expected in (
            "/api/admin/roadmap-review/metrics",
            "/api/admin/roadmap-review/notify/{case_id}",
        ):
            assert expected in paths, f"{expected} would 405 in production"
