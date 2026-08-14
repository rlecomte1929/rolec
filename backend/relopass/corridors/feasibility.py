"""Is there still enough runway to run this corridor? (AIQ-1748 / AIQ-1745)

Free-movement corridors are move-date anchored: the employee flies, then registers.
Employment-permit corridors invert that — the permit and the entry visa must both be
granted *before* travel, so the real constraint is how much runway exists between
today and the intended start date. Open an ES_IE case six weeks out and no amount of
diligence recovers it: the DETE permit alone is 35 days and the 'D' visa another 40.

That is the "week-seven ambush" the product exists to surface in week one.

The measurement is the longest path from any root step to the corridor's declared
``arrival_anchor`` (AIQ-1747). Deriving it from the graph rather than hardcoding a
threshold has three consequences worth stating, because they are the whole design:

1. **Free-movement corridors exclude themselves.** Their graphs root *at* arrival, so
   the pre-arrival path is 0–1 days. No allowlist, no corridor special-casing, and
   nothing to keep in sync when a corridor is added.
2. **It self-corrects.** When real ES_IE lead times land (AIQ-1746), the threshold
   moves with the step durations. Nobody has to remember to update a constant.
3. **New permit corridors get it free.** IN_DE (Blue Card, 158 days) is covered
   without a line of corridor-specific code.

Note that ``petitioning_party`` cannot serve as the permit-vs-free-movement
discriminator: every corridor declares ``EMPLOYEE``, ES_IE included. Branching on it
compiles, reads plausibly, and does nothing.

Pure functions over the loader's frozen dataclasses — no DB, no clock, no ``app/``
import, ``today`` always injected. Same contract as the sibling ``scheduler``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from .loader import CorridorStep
from .scheduler import schedule_steps

# A corridor with less pre-arrival runway than this is not lead-time constrained at
# all — a one-day flight is not a planning problem. Free-movement corridors measure
# 0–1 days and permit corridors 104–158, so the gap this sits in is enormous; it is a
# guard against warning on noise, not a tuned parameter.
MIN_MATERIAL_LEAD_DAYS = 7

# How much headroom above the required runway still counts as uncomfortable. Mirrors
# scheduler.AMBER_THRESHOLD_DAYS, which plays the same role for per-step deadlines.
TIGHT_BUFFER_DAYS = 14

# Verdict vocabulary. Deliberately distinct from scheduler's per-step flag names
# (green/amber/red_late): this is one verdict about the case as a whole, not a
# classification of an individual step's deadline.
CRITICAL = "critical"  # not enough runway — the timeline cannot be met
TIGHT = "tight"        # enough, but with no slack for any delay
OK = "ok"              # comfortable, or the corridor has no material lead time


@dataclass(frozen=True)
class FeasibilityAssessment:
    """Whether a case's target start date leaves room for the corridor to run."""

    verdict: str
    required_days: int
    available_days: int
    derivation: str

    @property
    def is_warning(self) -> bool:
        return self.verdict in (CRITICAL, TIGHT)


def arrival_anchor_step(steps: Sequence[CorridorStep]) -> Optional[CorridorStep]:
    """The step marking the end of the pre-arrival runway, or None if undeclared.

    A corridor that declares no anchor is not an error — it simply cannot be
    assessed, and every caller degrades to "no opinion" rather than guessing.
    """
    for step in steps:
        if step.arrival_anchor:
            return step
    return None


def required_lead_time_days(steps: Sequence[CorridorStep]) -> int:
    """Days of work that must happen before the employee is in the destination.

    The longest path from any root step to the ``arrival_anchor``, inclusive of the
    anchor's own duration. 0 when no anchor is declared, or when the anchor is itself
    a root (a free-movement corridor, where nothing precedes arrival).

    Reuses ``scheduler.schedule_steps``, so it inherits that function's cycle
    detection: a corridor graph with a cycle raises rather than looping.
    """
    anchor = arrival_anchor_step(steps)
    if anchor is None:
        return 0
    base = date(2000, 1, 1)  # arbitrary origin; only the delta is meaningful
    schedule = schedule_steps(steps, base)
    if anchor.step_id not in schedule:
        return 0
    return max(0, (schedule[anchor.step_id] - base).days)


def assess_feasibility(
    steps: Sequence[CorridorStep],
    target_start_date: Optional[date],
    today: date,
) -> Optional[FeasibilityAssessment]:
    """Assess whether ``target_start_date`` leaves room for this corridor to run.

    Returns None when there is nothing to say — no target date, or a corridor with no
    declared arrival anchor. Callers render nothing in that case; an absent opinion
    must never be shown as reassurance.

    A corridor whose pre-arrival runway is below ``MIN_MATERIAL_LEAD_DAYS`` always
    returns ``OK``: free movement imposes no lead-time constraint, so warning about
    one would be false.
    """
    if target_start_date is None:
        return None

    anchor = arrival_anchor_step(steps)
    if anchor is None:
        return None

    required = required_lead_time_days(steps)
    available = (target_start_date - today).days

    if required < MIN_MATERIAL_LEAD_DAYS:
        return FeasibilityAssessment(
            verdict=OK,
            required_days=required,
            available_days=available,
            derivation=(
                f"No material pre-arrival lead time: nothing must complete before "
                f"“{anchor.name}”."
            ),
        )

    if available < required:
        verdict = CRITICAL
    elif available < required + TIGHT_BUFFER_DAYS:
        verdict = TIGHT
    else:
        verdict = OK

    shortfall = required - available
    detail = {
        CRITICAL: f" — {shortfall} day{'s' if shortfall != 1 else ''} short",
        TIGHT: f" — only {available - required} day{'s' if available - required != 1 else ''} of slack",
        OK: "",
    }[verdict]

    return FeasibilityAssessment(
        verdict=verdict,
        required_days=required,
        available_days=available,
        derivation=(
            f"{required} days of steps must complete before “{anchor.name}”; "
            f"{available} days remain until the target start date{detail}."
        ),
    )
