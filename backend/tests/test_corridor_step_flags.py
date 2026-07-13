"""Retrospective flagging (Gap 3).

The engine assumed a future move date, so the worst flag it could produce was
amber ("tight window"). The real validation case has a mover who has ALREADY
departed, which means several windows may already be breached. An engine that
cannot say "you are late" cannot deliver the product thesis — the week-seven
ambush surfaced in week one.

Two things pinned here:
  1. An elapsed, unmet window flags `red_late` — not amber, not silence.
  2. A `nothing_to_do` step flags `confirmed` — a positive, never a risk colour
     and never a blank row (which reads as a broken screen).
"""
from __future__ import annotations

from datetime import date, timedelta

from backend.relopass.corridors.loader import CorridorStep
from backend.relopass.corridors.scheduler import (
    classify_step_flags,
    compute_deadlines,
    schedule_steps,
    triage_summary,
)

DEPARTED = "DEPART_NO"
TODAY = date(2026, 7, 13)


def _steps():
    return [
        CorridorStep(
            step_id=DEPARTED,
            name="Depart Norway",
            responsible_party="EMPLOYEE",
            expected_duration_days=0,
        ),
        CorridorStep(
            step_id="A1_FOLKEREGISTER",
            name="Report move abroad to Folkeregisteret",
            responsible_party="EMPLOYEE",
            expected_duration_days=1,
            prerequisite_step_ids=(DEPARTED,),
            time_window_relative_to=DEPARTED,
            time_window_min_days=0,
            time_window_max_days=8,
        ),
        CorridorStep(
            step_id="C0_DOMICILE",
            name="Establish proof of address",
            responsible_party="EMPLOYEE",
            expected_duration_days=3,
            prerequisite_step_ids=(DEPARTED,),
        ),
        CorridorStep(
            step_id="C1_CPAM",
            name="Register with CPAM",
            responsible_party="EMPLOYEE",
            expected_duration_days=14,
            prerequisite_step_ids=("C0_DOMICILE",),
            time_window_relative_to=DEPARTED,
            time_window_min_days=0,
            time_window_max_days=90,
        ),
        CorridorStep(
            step_id="C2_RIGHT_OF_RETURN",
            name="Right to enter & reside",
            responsible_party="EMPLOYEE",
            expected_duration_days=0,
            outcome_type="nothing_to_do",
        ),
        CorridorStep(
            step_id="A7_PENSION",
            name="Preserve accrued Norwegian pension rights",
            responsible_party="EMPLOYEE",
            expected_duration_days=0,
            prerequisite_step_ids=(DEPARTED,),
            # No time window: the corridor states no deadline, so we invent none.
        ),
    ]


def _flags(*, departed_days_ago: int, done=(), today: date = TODAY):
    steps = _steps()
    departure = today - timedelta(days=departed_days_ago)
    # Departure already happened, on a known past date. That real completion is
    # the anchor — which is what lets downstream windows land in the past.
    actuals = {DEPARTED: departure}
    schedule = schedule_steps(steps, departure, actual_completions=actuals)
    deadlines = compute_deadlines(steps, departure, schedule=schedule)
    return classify_step_flags(
        steps,
        schedule=schedule,
        deadlines=deadlines,
        today=today,
        completed_step_ids=set(done) | {DEPARTED},
    )


class TestRedLate:
    def test_elapsed_window_not_done_is_red_late(self):
        # Departed 30 days ago; the Folkeregister window closed after 8.
        assert _flags(departed_days_ago=30)["A1_FOLKEREGISTER"] == "red_late"

    def test_elapsed_window_already_done_is_green_not_red(self):
        flags = _flags(departed_days_ago=30, done=["A1_FOLKEREGISTER"])
        assert flags["A1_FOLKEREGISTER"] == "green"

    def test_window_still_open_is_not_red(self):
        assert _flags(departed_days_ago=2)["A1_FOLKEREGISTER"] != "red_late"


class TestNothingToDo:
    def test_nothing_to_do_is_confirmed(self):
        assert _flags(departed_days_ago=30)["C2_RIGHT_OF_RETURN"] == "confirmed"

    def test_never_reads_as_risk_however_long_elapsed(self):
        assert _flags(departed_days_ago=400)["C2_RIGHT_OF_RETURN"] == "confirmed"


class TestBlocked:
    def test_unmet_prerequisite_is_blocked(self):
        # C1 (CPAM) depends on C0 (proof of address), which isn't done. Its own
        # 90-day window has NOT elapsed, so blocked is the honest answer.
        assert _flags(departed_days_ago=30)["C1_CPAM"] == "blocked"

    def test_completing_the_prerequisite_unblocks(self):
        flags = _flags(departed_days_ago=30, done=["C0_DOMICILE"])
        assert flags["C1_CPAM"] != "blocked"

    def test_blocked_beats_late_so_we_dont_blame_the_employee_for_our_ordering(self):
        # 200 days elapsed: C1's window is long gone, but C0 still isn't done.
        # Reporting "you are late" for something not yet actionable is a lie.
        assert _flags(departed_days_ago=200)["C1_CPAM"] == "blocked"


class TestNoDeadline:
    def test_step_without_a_time_window_gets_no_deadline(self):
        # The corridor states no deadline for preserving pension rights, so the
        # engine must not invent one.
        assert _flags(departed_days_ago=30)["A7_PENSION"] == "no_deadline"


class TestTimeMovesTheFlagWithoutRegeneration:
    """Flags are computed on read, so crossing a window boundary flips
    amber -> red_late with no cron and no regenerate."""

    def test_amber_becomes_red_late_as_the_window_passes(self):
        assert _flags(departed_days_ago=5)["A1_FOLKEREGISTER"] == "amber"
        assert _flags(departed_days_ago=12)["A1_FOLKEREGISTER"] == "red_late"


class TestTriageSummary:
    def test_counts_every_key_even_at_zero(self):
        counts = triage_summary(_flags(departed_days_ago=30))
        assert counts["red_late"] == 1      # A1
        assert counts["confirmed"] == 1     # C2
        assert counts["blocked"] == 1       # C1
        assert counts["no_deadline"] == 2   # C0 and A7 — neither states a deadline
        assert counts["green"] == 1         # the departure itself, done
        assert counts["amber"] == 0
        # Every key present even at zero, so the UI never has to guess whether a
        # missing key means "none" or means "broken".
        assert set(counts) == {"red_late", "amber", "blocked", "green", "confirmed", "no_deadline"}
