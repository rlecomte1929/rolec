"""[AIQ-1526] The safety-net sweep that (re)notifies HR about stuck roadmaps.

The instant-fire notify covers the normal path. This sweep covers the case where the
roadmap build HANGS and the notify line is never reached — the employee is blocked and HR
was never told. The sweep re-runs the idempotent notify over every held, never-notified,
REAL roadmap.

The tests that matter most:
  * an orphan (held review row whose case was purged — no milestones) is NEVER touched
  * an already-notified case is not re-mailed
  * one bad case does not abort the whole sweep
"""
from __future__ import annotations

import os

os.environ["RELOPASS_QUERY_COUNTER_OFF"] = "1"

from backend.app.services import roadmap_review_sweep as sweep


def _stub_candidates(monkeypatch, case_ids):
    """Bypass the DB query; drive the sweep off a fixed candidate list."""
    monkeypatch.setattr(sweep, "_pending_unnotified_case_ids", lambda limit: list(case_ids))


def _capture_notifies(monkeypatch, outcomes):
    """Record every notify call; return the status keyed in `outcomes` (default 'sent')."""
    called = []

    def _fake(case_id, *, dry_run=False, **_kw):
        called.append((case_id, dry_run))
        return {"status": outcomes.get(case_id, "sent"), "case_id": case_id}

    monkeypatch.setattr(
        "backend.app.services.roadmap_review_notification.notify_hr_roadmap_pending", _fake
    )
    return called


class TestTheSweepNotifiesRealStuckRoadmaps:
    def test_it_calls_notify_for_each_candidate(self, monkeypatch):
        _stub_candidates(monkeypatch, ["c1", "c2"])
        called = _capture_notifies(monkeypatch, {})

        result = sweep.run_roadmap_review_notify_sweep()

        assert [c for c, _ in called] == ["c1", "c2"]
        assert result["swept"] == 2
        assert result["sent"] == 2

    def test_dry_run_threads_through_and_sends_nothing(self, monkeypatch):
        _stub_candidates(monkeypatch, ["c1"])
        called = _capture_notifies(monkeypatch, {})

        result = sweep.run_roadmap_review_notify_sweep(dry_run=True)

        assert called == [("c1", True)], "dry_run must reach the notify call"
        assert result["dry_run"] is True


class TestOrphansAndAlreadyNotifiedAreNotDisturbed:
    """The query is what excludes orphans (no milestones) and already-notified rows
    (notified_at IS NOT NULL). If the candidate list is empty, the sweep touches nothing —
    it must not invent work."""

    def test_no_candidates_means_no_notifies(self, monkeypatch):
        _stub_candidates(monkeypatch, [])
        called = _capture_notifies(monkeypatch, {})

        result = sweep.run_roadmap_review_notify_sweep()

        assert called == []
        assert result == {
            "swept": 0, "sent": 0, "unreachable": 0, "failed": 0,
            "already_notified": 0, "dry_run": False,
        }

    def test_the_query_filters_on_held_unnotified_and_real(self):
        """Pin the three predicates in the SQL so a future edit can't silently drop the
        orphan guard (EXISTS milestones) or start re-mailing notified/released cases."""
        import inspect

        src = inspect.getsource(sweep._pending_unnotified_case_ids)
        assert "released_to_user IS FALSE" in src
        assert "notified_at IS NULL" in src
        assert "case_milestones" in src and "EXISTS" in src, (
            "the orphan guard — a real roadmap has milestones; a purged-case orphan does not"
        )


class TestTheSweepStaysGreen:
    def test_one_failing_case_does_not_abort_the_rest(self, monkeypatch):
        _stub_candidates(monkeypatch, ["ok1", "boom", "ok2"])

        def _fake(case_id, *, dry_run=False, **_kw):
            if case_id == "boom":
                raise RuntimeError("notify blew up")
            return {"status": "sent", "case_id": case_id}

        monkeypatch.setattr(
            "backend.app.services.roadmap_review_notification.notify_hr_roadmap_pending", _fake
        )

        result = sweep.run_roadmap_review_notify_sweep()

        assert result["swept"] == 3
        assert result["sent"] == 2, "the two good cases still send"
        assert result["failed"] == 1, "the blow-up is counted, not raised"

    def test_a_broken_query_yields_an_empty_sweep_not_a_crash(self, monkeypatch):
        def _boom(_limit):
            raise RuntimeError("db down")

        # Exercise the real function's try/except via a broken engine.
        monkeypatch.setattr(sweep, "_engine", lambda: (_ for _ in ()).throw(RuntimeError("db")))
        assert sweep._pending_unnotified_case_ids(10) == []

    def test_status_tally_maps_to_the_result_shape(self, monkeypatch):
        _stub_candidates(monkeypatch, ["s", "u", "f", "e", "a"])
        _capture_notifies(monkeypatch, {
            "s": "sent", "u": "unreachable", "f": "failed", "e": "error", "a": "already_notified",
        })

        result = sweep.run_roadmap_review_notify_sweep()

        assert result["sent"] == 1
        assert result["unreachable"] == 1
        assert result["failed"] == 2, "failed + error both count as undelivered"
        assert result["already_notified"] == 1


class TestTheCronRouteIsRegisteredWhereProdBoots:
    """Render runs `uvicorn backend.main:app`. A cron registered only in the modular app
    405s in production."""

    def test_prod_app_exposes_the_sweep_route(self):
        from backend.main import app

        paths = {r.path for r in app.routes}
        assert "/api/crons/roadmap-review-notify" in paths, "would 405 in production"
