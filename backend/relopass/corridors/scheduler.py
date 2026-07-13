"""Server-side date math for corridor step graphs (C1-05 / C2-07).

The StepGraph (C2-07) must NEVER recompute deadlines in JS — they are derived
here, server-side, from the corridor step graph + a case's target_arrival_date.

Two outputs:

1. ``schedule_steps`` — a forward topological projection: each step's expected
   completion date = max(prerequisite completions, project base) +
   ``expected_duration_days``. This is what makes delay-propagation work: extend
   any upstream step's duration and every downstream date shifts by the same
   amount (C2-07 validation criterion 4).

2. ``compute_deadlines`` — the *rule-anchored* deadlines: for every step that
   carries a ``time_window_relative_to`` anchor, the deadline is
   ``anchor_completion + time_window_max_days`` (falling back to
   ``time_window_min_days``), with a human-readable ``derivation`` string. Steps
   without a time window have no legal deadline (we do NOT fabricate one).

Pure functions over the loader's frozen ``CorridorStep`` dataclasses — no DB, no
clock, fully unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Mapping, Optional, Sequence, Set

from .loader import CorridorStep


@dataclass(frozen=True)
class ComputedDeadline:
    """A rule-anchored deadline derived for one step of one case."""

    step_id: str
    due_date: date
    derivation: str


def _topological_order(steps: Sequence[CorridorStep]) -> List[CorridorStep]:
    """Kahn's algorithm over ``prerequisite_step_ids``. Raises on a cycle."""
    by_id: Dict[str, CorridorStep] = {s.step_id: s for s in steps}
    indegree: Dict[str, int] = {s.step_id: 0 for s in steps}
    dependents: Dict[str, List[str]] = {s.step_id: [] for s in steps}
    for s in steps:
        for prereq in s.prerequisite_step_ids:
            if prereq in by_id:  # ignore dangling refs (loader already guards them)
                indegree[s.step_id] += 1
                dependents[prereq].append(s.step_id)

    queue = [sid for sid, d in indegree.items() if d == 0]
    ordered: List[str] = []
    while queue:
        sid = queue.pop(0)
        ordered.append(sid)
        for dep in dependents[sid]:
            indegree[dep] -= 1
            if indegree[dep] == 0:
                queue.append(dep)

    if len(ordered) != len(steps):
        raise ValueError("corridor step graph has a cycle; cannot schedule")
    return [by_id[sid] for sid in ordered]


def schedule_steps(
    steps: Sequence[CorridorStep],
    base_date: date,
    *,
    actual_completions: Optional[Mapping[str, date]] = None,
) -> Dict[str, date]:
    """Project each step's expected completion date.

    Root steps (no in-graph prerequisites) start at ``base_date``; every other
    step completes ``expected_duration_days`` after the latest of its
    prerequisites. Returns ``{step_id: completion_date}``.

    ``actual_completions`` overrides the projection for steps that have really
    happened, on the date they really happened. This is what makes the engine
    work *retrospectively*: for a mover who has already left, departure is a
    completed step with a known past date, so every window anchored to it is
    computed from that real date and can therefore land in the past — which is
    how a deadline can be reported as already missed rather than merely "tight".
    """
    by_id = {s.step_id: s for s in steps}
    actuals = dict(actual_completions or {})
    completion: Dict[str, date] = {}
    for step in _topological_order(steps):
        if step.step_id in actuals:
            completion[step.step_id] = actuals[step.step_id]
            continue
        prereq_dates = [
            completion[p] for p in step.prerequisite_step_ids if p in by_id
        ]
        start = max(prereq_dates) if prereq_dates else base_date
        duration = step.expected_duration_days or 0
        completion[step.step_id] = start + timedelta(days=duration)
    return completion


def compute_deadlines(
    steps: Sequence[CorridorStep],
    base_date: date,
    *,
    schedule: Optional[Mapping[str, date]] = None,
) -> List[ComputedDeadline]:
    """Rule-anchored deadlines for the time-windowed steps only.

    A step earns a deadline iff it sets ``time_window_relative_to``. The due date
    is the anchor step's completion + ``time_window_max_days`` (or
    ``time_window_min_days`` when no max is set). Steps with no time window get
    no deadline — we never invent a legal deadline that the corridor didn't state.
    """
    by_id = {s.step_id: s for s in steps}
    sched = dict(schedule) if schedule is not None else schedule_steps(steps, base_date)
    out: List[ComputedDeadline] = []
    for step in steps:
        anchor_id = step.time_window_relative_to
        if not anchor_id:
            continue
        window_days = step.time_window_max_days
        if window_days is None:
            window_days = step.time_window_min_days
        if window_days is None or anchor_id not in sched:
            continue
        anchor_date = sched[anchor_id]
        due = anchor_date + timedelta(days=window_days)
        anchor_name = by_id[anchor_id].name if anchor_id in by_id else anchor_id
        lo = step.time_window_min_days
        hi = step.time_window_max_days
        if lo is not None and hi is not None:
            window_phrase = f"within {lo}–{hi} days"
        else:
            window_phrase = f"within {window_days} days"
        derivation = f"{window_phrase} of “{anchor_name}”"
        if step.cite:
            derivation += f" (per {step.cite})"
        out.append(
            ComputedDeadline(step_id=step.step_id, due_date=due, derivation=derivation)
        )
    return out


# How close to a deadline counts as "tight" rather than comfortable.
AMBER_THRESHOLD_DAYS = 14

# Flag vocabulary.
CONFIRMED = "confirmed"      # nothing_to_do — a positive, never a risk colour
GREEN = "green"              # done, or comfortably ahead
AMBER = "amber"              # window open and closing
RED_LATE = "red_late"        # window elapsed and NOT done — already missed
BLOCKED = "blocked"          # a prerequisite isn't done yet
NO_DEADLINE = "no_deadline"  # the corridor states no deadline; we invent none


def classify_step_flags(
    steps: Sequence[CorridorStep],
    *,
    schedule: Mapping[str, date],
    deadlines: Sequence[ComputedDeadline],
    today: date,
    completed_step_ids: Optional[Set[str]] = None,
    amber_threshold_days: int = AMBER_THRESHOLD_DAYS,
) -> Dict[str, str]:
    """Classify every step against ``today``.

    The engine previously assumed a future move date, so the worst thing it could
    say was "tight". The real case is a mover who has ALREADY departed, whose
    windows may already be breached — and an engine that cannot say "you are
    late" cannot deliver the product's whole premise.

    Pure: no DB, no clock (``today`` is injected). Because these flags are derived
    on read rather than materialised, an amber step becomes ``red_late`` the moment
    its window passes, with no cron and no regeneration.
    """
    done = set(completed_step_ids or ())
    due_by_step = {d.step_id: d.due_date for d in deadlines}
    flags: Dict[str, str] = {}

    for step in steps:
        # A step that asks nothing of anyone is a confirmation, whatever the
        # clock says. It must never render as a risk — or as a blank row, which
        # a reader cannot distinguish from a broken screen.
        if step.outcome_type == "nothing_to_do":
            flags[step.step_id] = CONFIRMED
            continue

        if step.step_id in done:
            flags[step.step_id] = GREEN
            continue

        # An unmet prerequisite dominates: the step cannot be actioned yet, so
        # reporting it as late would blame the employee for our own ordering.
        if any(p not in done for p in step.prerequisite_step_ids):
            flags[step.step_id] = BLOCKED
            continue

        due = due_by_step.get(step.step_id)
        if due is None:
            flags[step.step_id] = NO_DEADLINE
            continue

        if today > due:
            flags[step.step_id] = RED_LATE
        elif (due - today).days <= amber_threshold_days:
            flags[step.step_id] = AMBER
        else:
            flags[step.step_id] = GREEN

    return flags


def triage_summary(flags: Mapping[str, str]) -> Dict[str, int]:
    """Counts per flag, for the triage band. Always contains every key, so the
    UI never has to guess whether a missing key means zero or means broken."""
    keys = (RED_LATE, AMBER, BLOCKED, GREEN, CONFIRMED, NO_DEADLINE)
    counts = {k: 0 for k in keys}
    for flag in flags.values():
        if flag in counts:
            counts[flag] += 1
    return counts
