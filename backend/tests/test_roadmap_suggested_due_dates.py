"""[AIQ-1258c] Suggested roadmap due dates.

The live employee roadmap (GET /api/cases/{id}/roadmap/tracks) projects steps
from case_forms. Steps with a real form deadline keep it; steps with no
deadline get a *suggested* due date computed as ``move_date − track lead time``
(from backend.app.services.roadmap_lead_times). These tests pin that mapping
decision via the pure helper `_suggested_due_date` so it can't regress without
also touching the read-time loop in cases_read.get_case_roadmap_tracks.
"""
import datetime

from backend.app.routers.cases_read import _suggested_due_date
from backend.app.services.roadmap_lead_times import lead_time_days_for


MOVE_DATE = datetime.date(2026, 9, 1)


def test_no_deadline_with_move_date_gets_suggested():
    """A step with no deadline + a known move date gets a computed suggested
    date and the flag set True."""
    lead = lead_time_days_for("visa")
    assert lead is not None
    expected = (MOVE_DATE - datetime.timedelta(days=lead)).isoformat()

    due_date, is_suggested = _suggested_due_date(None, "visa", MOVE_DATE)

    assert is_suggested is True
    assert due_date == expected
    assert due_date == "2026-06-03"  # 2026-09-01 − 90 days


def test_existing_deadline_is_kept_and_not_flagged():
    """A step WITH a real deadline keeps it; the flag stays False even when a
    move date is available (a real deadline is never overwritten)."""
    due_date, is_suggested = _suggested_due_date("2026-08-15", "visa", MOVE_DATE)

    assert is_suggested is False
    assert due_date == "2026-08-15"


def test_no_move_date_no_suggestion():
    """No move date → no suggestion (never guess); flag False, due_date None."""
    due_date, is_suggested = _suggested_due_date(None, "visa", None)

    assert is_suggested is False
    assert due_date is None


def test_unknown_track_key_no_suggestion():
    """Unknown track/category key (no lead time) → no suggestion, even with a
    move date."""
    assert lead_time_days_for("not-a-real-key") is None

    due_date, is_suggested = _suggested_due_date(None, "not-a-real-key", MOVE_DATE)

    assert is_suggested is False
    assert due_date is None


def test_per_track_lead_times_differ():
    """Each track bucket subtracts its own lead time from the move date."""
    civil_due, _ = _suggested_due_date(None, "civil", MOVE_DATE)
    settlement_due, _ = _suggested_due_date(None, "settlement", MOVE_DATE)

    # civil lead = 30 days, settlement = 45 days (see roadmap_lead_times)
    assert civil_due == (MOVE_DATE - datetime.timedelta(days=30)).isoformat()
    assert settlement_due == (MOVE_DATE - datetime.timedelta(days=45)).isoformat()
    assert civil_due != settlement_due
