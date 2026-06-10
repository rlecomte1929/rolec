"""
W2-2 (HR-MVP): timeline SLA rule for HR cases.

A small, pure, dependency-free function so it's trivially unit-testable and can be
called from the legacy db layer (backend/db/cases.py) without inverting the
import direction (database code must not import the app/ layer).

v1 deliberately derives SLA from data the cockpit query ALREADY has — the
relocation target move date, task-completion %, and case status — rather than
joining per-corridor step durations (rce.steps / corridor YAML), which is a v2
enhancement. Risk (budget/overdue) is a separate, already-existing signal
(case_assignments.risk_status); this is the timeline lens, not a replacement.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Tuple

# Tunables for the v1 rule.
AT_RISK_WINDOW_DAYS = 30   # move within this window …
AT_RISK_PCT = 80           # … and below this completion % ⇒ at risk
_DONE_STATUSES = {"completed", "complete", "closed", "cancelled", "archived"}


def _parse_date(value: object) -> Optional[date]:
    """Best-effort date parse; returns None on anything unparseable."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def compute_sla_status(
    target_move_date: object,
    tasks_done_pct: object,
    status: object,
    *,
    today: Optional[date] = None,
    at_risk_window_days: Optional[int] = None,
    at_risk_pct: Optional[int] = None,
) -> Tuple[Optional[str], Optional[int]]:
    """
    Returns (sla_status, days_until_move):
      - 'overdue'  : move date has passed and the case is not done
      - 'at_risk'  : move within the at-risk window and < the at-risk % tasks done
      - 'on_track' : otherwise (incl. done cases and far-out moves)
      - None       : no target move date (unknown — render nothing)

    days_until_move is signed (negative = the move date is in the past), or None
    when there is no target move date.

    I-3 Stage 4: ``at_risk_window_days`` / ``at_risk_pct`` override the module
    defaults per call (e.g. a corridor-specific SLA resolved by the app layer).
    Both None → the AT_RISK_WINDOW_DAYS / AT_RISK_PCT module constants, so the
    function stays pure (no app/ import) and backward-compatible.
    """
    window = AT_RISK_WINDOW_DAYS if at_risk_window_days is None else int(at_risk_window_days)
    pct_threshold = AT_RISK_PCT if at_risk_pct is None else int(at_risk_pct)
    moved = _parse_date(target_move_date)
    if moved is None:
        return None, None

    ref = today or date.today()
    days = (moved - ref).days

    st = (str(status) if status is not None else "").strip().lower()
    if st in _DONE_STATUSES:
        return "on_track", days

    try:
        pct = int(tasks_done_pct)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        pct = 0

    if days < 0:
        return "overdue", days
    if days <= window and pct < pct_threshold:
        return "at_risk", days
    return "on_track", days
