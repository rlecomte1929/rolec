"""W2-2 — unit tests for the pure timeline-SLA rule (backend/sla_rules.py)."""
from __future__ import annotations

from datetime import date

from backend.sla_rules import compute_sla_status

TODAY = date(2026, 6, 10)


def test_no_move_date_is_unknown():
    assert compute_sla_status(None, 10, "active", today=TODAY) == (None, None)
    assert compute_sla_status("", 10, "active", today=TODAY) == (None, None)


def test_past_move_date_not_done_is_overdue():
    s, days = compute_sla_status("2026-06-01", 50, "active", today=TODAY)
    assert s == "overdue" and days == -9


def test_near_move_low_completion_is_at_risk():
    # 20 days out, 40% done → at risk
    s, days = compute_sla_status("2026-06-30", 40, "active", today=TODAY)
    assert s == "at_risk" and days == 20


def test_near_move_high_completion_is_on_track():
    # 20 days out but 85% done → on track
    s, _ = compute_sla_status("2026-06-30", 85, "active", today=TODAY)
    assert s == "on_track"


def test_far_move_is_on_track_regardless_of_pct():
    s, days = compute_sla_status("2026-12-01", 0, "active", today=TODAY)
    assert s == "on_track" and days == 174


def test_done_case_is_on_track_even_if_past():
    # completed cases never show overdue/at-risk
    s, _ = compute_sla_status("2026-01-01", 100, "completed", today=TODAY)
    assert s == "on_track"
    s2, _ = compute_sla_status("2026-06-30", 10, "closed", today=TODAY)
    assert s2 == "on_track"


def test_non_numeric_pct_treated_as_zero():
    s, _ = compute_sla_status("2026-06-30", None, "active", today=TODAY)
    assert s == "at_risk"  # 20 days out, 0% → at risk


def test_accepts_datetime_string_and_date_object():
    assert compute_sla_status("2026-06-30T00:00:00Z", 0, "active", today=TODAY)[0] == "at_risk"
    assert compute_sla_status(date(2026, 6, 30), 0, "active", today=TODAY)[0] == "at_risk"
