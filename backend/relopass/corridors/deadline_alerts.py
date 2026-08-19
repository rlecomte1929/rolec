"""Deadline-alert windows, the one-tag-one-destination invariant, and copy.

Three pure concerns, none of which touch a DB or a clock:

1. :func:`due_alerts` — given a corridor's steps, their computed deadlines and
   ``today``, which alerts are inside their firing window right now.
2. :func:`check_tag_destination_invariant` — the content gate. An alert tag maps
   to exactly ONE destination's rule set, enforced across every corridor at once.
3. :func:`render_alert` — the message, assembled only from what the corridor
   itself authored.

Why the invariant is enforced rather than documented
----------------------------------------------------
Norway requires an anti-echinococcus treatment in a 24–120h window before
arrival; France requires none and instead mandates I-CAD registration within 7
days of arrival. A single tag bound to both destinations' dog-import steps forces
copy that is either wrong for half its readers or too vague to act on. That is
not a hypothetical — it shipped, and the fix was to split the tag by destination.
A rule that only lives in a document gets re-broken by the next author, so it
lives here, with a repo-wide test behind it.

Note the split boundary: ``tag`` selects COPY, ``step_id`` is the ledger key.
Renaming a tag re-points a message and re-fires nothing. Renaming a step_id
changes the idempotency key and re-fires history — so tags are safe to split,
step ids are not.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .loader import CorridorAgent, CorridorStep
from .scheduler import ComputedDeadline


class DeadlineTagConflict(Exception):
    """Raised when one alert tag is bound to more than one rule set."""


@dataclass(frozen=True)
class DueAlert:
    """One step whose alert window contains ``today``.

    ``due_date`` is the statutory deadline; ``trigger_date`` is when the window
    opened. ``days_remaining`` is inclusive of today — on the due date itself it
    is 0, and the copy says the window closes today rather than that it has passed.
    """

    step_id: str
    tag: str
    label: str
    channel: str
    lead_days: int
    due_date: date
    trigger_date: date
    days_remaining: int
    responsible_party: str
    step_name: str
    derivation: str
    cite: Optional[str]


def event_uid(case_ref: str, step_id: str, due_date: date) -> str:
    """The ledger's idempotency key: ``<case>|<step>|<due-date>``.

    Keyed on the DUE DATE, not on the send date, so re-running the sweep — twice
    in a day, or after a crash — cannot re-fire. If the case's move date moves,
    the due date moves with it and the alert is a genuinely new obligation, which
    is why the date belongs in the key rather than beside it.
    """
    return f"{case_ref}|{step_id}|{due_date.isoformat()}"


def due_alerts(
    steps: Sequence[CorridorStep],
    deadlines: Sequence[ComputedDeadline],
    *,
    today: date,
    completed_step_ids: Optional[Set[str]] = None,
) -> List[DueAlert]:
    """Alerts whose window ``[due - lead_days, due]`` contains ``today``.

    Pure: ``today`` is injected, never read from the clock, so the same inputs
    always give the same output — which is what lets the sweep be replayed and
    tested at a boundary.

    A step already completed raises nothing: the obligation is discharged. A step
    past its due date raises nothing either — that is lateness, which the step
    flags already report as ``red_late``; an alert saying "your window is open"
    would be false.
    """
    done = set(completed_step_ids or ())
    due_by_step = {d.step_id: d for d in deadlines}
    out: List[DueAlert] = []

    for step in steps:
        trigger = step.deadline_trigger
        if trigger is None or step.step_id in done:
            continue
        computed = due_by_step.get(step.step_id)
        if computed is None:
            continue

        due = computed.due_date
        opens = due - timedelta(days=trigger.lead_days)
        if not (opens <= today <= due):
            continue

        out.append(
            DueAlert(
                step_id=step.step_id,
                tag=trigger.tag,
                label=trigger.label,
                channel=trigger.channel,
                lead_days=trigger.lead_days,
                due_date=due,
                trigger_date=opens,
                days_remaining=(due - today).days,
                responsible_party=step.responsible_party,
                step_name=step.name,
                derivation=computed.derivation,
                cite=step.cite,
            )
        )

    out.sort(key=lambda a: (a.due_date, a.step_id))
    return out


def check_tag_destination_invariant(
    corridors: Mapping[str, CorridorAgent],
) -> List[str]:
    """Return a list of invariant violations across every loaded corridor.

    Two rules, both instances of "one tag names one thing":

    - a tag bound to two different JURISDICTIONS — the rule sets differ by
      construction, so no single message can be correct for both. A step's
      jurisdiction is its corridor's destination unless the trigger declares
      otherwise (exit obligations are owed to the origin);
    - a tag bound to two different STEPS — one tag selects one message, so
      sharing it would send the same copy for two unrelated obligations.

    Returns violation strings rather than raising, so a caller can report every
    problem in one pass instead of the first one. :func:`assert_tag_invariant`
    is the raising wrapper.
    """
    # tag -> (destination, corridor_key, step_id) of its first binding.
    seen: Dict[str, Tuple[Optional[str], str, str]] = {}
    violations: List[str] = []

    for corridor_key in sorted(corridors):
        agent = corridors[corridor_key]
        for step in agent.step_graph:
            if step.deadline_trigger is None:
                continue
            # The rule set's owner — the destination for an entry obligation, the
            # declared jurisdiction for an exit one owed to the origin.
            destination = (
                step.deadline_trigger.jurisdiction or agent.destination_country_iso3
            )
            tag = step.deadline_trigger.tag
            prior = seen.get(tag)
            if prior is None:
                seen[tag] = (destination, corridor_key, step.step_id)
                continue
            prior_dest, prior_corridor, prior_step = prior
            if prior_dest != destination:
                violations.append(
                    f"tag {tag!r} is bound to two destinations: "
                    f"{prior_dest} (via {prior_corridor}.{prior_step}) and "
                    f"{destination} (via {corridor_key}.{step.step_id}). "
                    f"One tag = one destination's rule set — suffix the tag with "
                    f"the destination, e.g. {tag}-{str(destination or '')[:2].lower()}."
                )
            elif prior_step != step.step_id:
                violations.append(
                    f"tag {tag!r} is bound to two steps: "
                    f"{prior_corridor}.{prior_step} and {corridor_key}.{step.step_id}. "
                    f"One tag selects one message; give each step its own tag."
                )

    return violations


def assert_tag_invariant(corridors: Mapping[str, CorridorAgent]) -> None:
    """Raise :class:`DeadlineTagConflict` if any tag violates the invariant."""
    violations = check_tag_destination_invariant(corridors)
    if violations:
        raise DeadlineTagConflict(
            f"{len(violations)} deadline-tag invariant violation(s):\n  - "
            + "\n  - ".join(violations)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Copy
# ─────────────────────────────────────────────────────────────────────────────
#
# Assembled from the corridor's own authored step — its name, its window
# derivation, its citation. Nothing here states a legal fact the corridor did not
# already state, which is what keeps a new destination a data exercise: author the
# step, get correct copy.


def _window_phrase(days_remaining: int) -> str:
    """Window phrasing, never "due today".

    An alert fires across a window, not on a day. "Due today" on the first day of
    a 30-day window is false and teaches the reader to ignore the next one.
    """
    if days_remaining == 0:
        return "this window closes today"
    if days_remaining == 1:
        return "you have 1 day left in this window"
    return f"you have {days_remaining} days left in this window"


# Who the message speaks to. An HR-owned step addressed to the employee reads as
# a demand they cannot action; the reverse reads as someone else's problem.
_EMPLOYEE_PARTIES = ("EMPLOYEE", "EMPLOYEE_FAMILY")
_HR_PARTIES = ("EMPLOYER", "HR", "EMPLOYER_HR")


def render_alert(alert: DueAlert, *, destination: Optional[str] = None) -> Dict[str, str]:
    """Render one alert to ``{subject, body}``.

    Owner-aware: an employee-owned step speaks to the reader, an HR-owned step
    says who needs to act, and an authority-owned step is a wait, not a task.
    """
    party = (alert.responsible_party or "").upper()
    window = _window_phrase(alert.days_remaining)

    if party in _EMPLOYEE_PARTIES:
        opening = f"{alert.step_name} — {window}."
        action = "This one is yours to complete."
    elif party in _HR_PARTIES:
        opening = f"{alert.step_name} — {window}."
        action = "Your HR team needs to complete this one."
    elif party.startswith("AUTHORITY"):
        opening = f"{alert.step_name} — {window}."
        action = (
            "This sits with the authority, not with you. It is here so a slow "
            "decision is visible rather than silent."
        )
    else:
        opening = f"{alert.step_name} — {window}."
        action = f"Owner: {alert.responsible_party}."

    lines = [
        opening,
        action,
        f"Deadline: {alert.due_date.isoformat()} ({alert.derivation}).",
    ]
    if alert.cite:
        lines.append(f"Source: {alert.cite}.")

    subject = f"{alert.label} — {window}"
    return {"subject": subject, "body": "\n".join(lines)}
