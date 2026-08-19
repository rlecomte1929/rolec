"""Sweep-layer evals: stated skip reasons (E3) and exactly-once (E6).

These exercise ``plan_case_alerts``, the half of the sweep that needs no
database — a case dict and an injected ``today`` in, a decision out. That split
is deliberate: the properties worth pinning here are about judgement (what fires,
what is skipped and why), and running them against a database would test the
database instead.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.app.services.corridor_deadline_sweep import plan_case_alerts
from backend.relopass.corridors.deadline_alerts import event_uid

# FR_NO's EEA police registration: a 90-day window, 30 days' lead.
#
# The due date is pinned as a literal rather than recomputed here, so this file
# asserts a date instead of restating the engine's arithmetic back to itself.
# It is NOT move + 90: the window is anchored to TRAVEL_TO_NO, which carries a
# one-day duration, so the anchor lands the day after the move.
MOVE = date(2026, 3, 1)
DUE = date(2026, 5, 31)          # (MOVE + 1 day travel) + 90-day window
OPENS = DUE - timedelta(days=30)  # 2026-05-01


def _case(**kw):
    base = {
        "id": "case-1",
        "origin_country_code": "FR",
        "dest_country_code": "NO",
        "target_move_date": MOVE,
        "actual_move_date": None,
        "status": "active",
    }
    base.update(kw)
    return base


# ─────────────────────────────────────────────────────────────────────────────
# E3 — every skip states its reason; nothing is guessed
# ─────────────────────────────────────────────────────────────────────────────

def test_e3_case_without_a_move_date_is_skipped_with_a_reason():
    """The single most important refusal in the sweep.

    Defaulting the anchor to today would compute statutory deadlines off a date
    the case never asserted, and send an alert that is confidently wrong about a
    legal window. Note populate_rce_from_cases DOES default this way — the sweep
    reuses its corridor resolver but not its fallback.
    """
    result = plan_case_alerts(
        _case(target_move_date=None, actual_move_date=None), today=OPENS
    )
    assert result.alerts == []
    assert result.skip_reason == "no target_move_date or actual_move_date on the case"


def test_e3_case_on_an_unauthored_corridor_is_skipped_with_a_reason():
    result = plan_case_alerts(
        _case(origin_country_code="BR", dest_country_code="JP"), today=OPENS
    )
    assert result.alerts == []
    assert "no corridor pathway authored" in result.skip_reason
    assert "BR_JP" in result.skip_reason


def test_e3_a_country_spelled_by_name_still_resolves():
    """public.cases holds both 'NO' and 'NORWAY'. A name-spelled case must not
    silently fall out of coverage — which is why the sweep reuses the existing
    country-name map rather than carrying its own."""
    result = plan_case_alerts(
        _case(origin_country_code="FRANCE", dest_country_code="NORWAY"), today=OPENS
    )
    assert result.skip_reason is None
    assert [a.step_id for a in result.alerts] == ["EEA_POLICE_REGISTRATION"]


def test_e3_actual_move_date_is_used_when_target_is_absent():
    result = plan_case_alerts(
        _case(target_move_date=None, actual_move_date=MOVE), today=OPENS
    )
    assert result.skip_reason is None
    assert len(result.alerts) == 1


def test_e3_iso_string_dates_are_accepted():
    """Some rows come back as strings depending on the driver; a string date must
    not read as 'no move date' and silently skip the case."""
    result = plan_case_alerts(_case(target_move_date="2026-03-01"), today=OPENS)
    assert result.skip_reason is None
    assert len(result.alerts) == 1


# ─────────────────────────────────────────────────────────────────────────────
# E6 — window boundaries, end to end through a real corridor
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "today, expected, why",
    [
        (OPENS - timedelta(days=1), 0, "the day before the window opens"),
        (OPENS, 1, "the day it opens"),
        (DUE, 1, "the due date is inside the window"),
        (DUE + timedelta(days=1), 0, "past due is lateness, not an open window"),
    ],
)
def test_e6_boundaries_through_the_fr_no_corridor(today, expected, why):
    assert len(plan_case_alerts(_case(), today=today).alerts) == expected, why


def test_e6_planning_is_stable_across_runs_on_the_same_day():
    """The sweep's exactly-once guard is the ledger, but it can only work if the
    same day plans the same event_uid every time."""
    runs = [plan_case_alerts(_case(), today=OPENS) for _ in range(3)]
    uids = [
        [event_uid(r.case_ref, a.step_id, a.due_date) for a in r.alerts] for r in runs
    ]
    assert uids[0] == uids[1] == uids[2]
    assert uids[0] == [f"case-1|EEA_POLICE_REGISTRATION|{DUE.isoformat()}"]


def test_e6_the_same_event_uid_persists_across_the_whole_window():
    """Every day of the window must produce the SAME key, or the ledger cannot
    suppress the repeat and the alert fires daily for a month."""
    keys = set()
    day = OPENS
    while day <= DUE:
        for a in plan_case_alerts(_case(), today=day).alerts:
            keys.add(event_uid("case-1", a.step_id, a.due_date))
        day += timedelta(days=1)
    assert len(keys) == 1, keys


def test_e6_a_moved_deadline_is_a_new_event():
    """The counterpart: if the move date shifts, the obligation genuinely moved
    and must be allowed to fire again."""
    a = plan_case_alerts(_case(), today=OPENS).alerts[0]
    later = _case(target_move_date=MOVE + timedelta(days=30))
    b = plan_case_alerts(later, today=OPENS + timedelta(days=30)).alerts[0]
    assert event_uid("case-1", a.step_id, a.due_date) != event_uid(
        "case-1", b.step_id, b.due_date
    )
