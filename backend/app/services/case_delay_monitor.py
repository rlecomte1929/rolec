"""AIQ-378a (AIQ-816) — Case-delay signal service (read-only).

The foundation of the proactive immigration case-monitoring loop (parent AIQ-378,
design: ``docs/design/aiq-378-proactive-case-monitoring.md``). Scans active
immigration cases for milestones that are past their expected ``target_date`` and
not yet completed, and returns one delay signal per case for the downstream
nightly scan + alert dispatch (subtask b) and HR surface (subtask d) to consume.

Design rules carried from ``case_staleness_alert.py``:
  * **Read-only.** Never mutates case or milestone data.
  * **Inert without data.** Zero active cases / zero overdue milestones -> ``[]``.
    Safe to ship dormant (the AIQ-378 epic is gated post-pilot; this layer simply
    returns nothing until ``immigration_milestones`` is populated).
  * **Honest signals only.** ``days_behind`` is computed from real
    ``immigration_milestones.target_date``; a milestone with no ``target_date`` is
    never flagged (no fabricated ETAs).
  * **Configurable env thresholds, clamped.**

Source of truth (resolved during recon — design §5 left this open):
  ``public.immigration_milestones`` (the AIQ-379 partner-sync table) — per-milestone
  ``target_date`` (expected) + ``status`` + ``completed_date``; ``milestone_type`` is
  the stage. Active cases = ``relocation_cases.status = 'active'`` joined on
  ``relocation_cases.id::text = immigration_milestones.case_id``. Milestone status
  vocabulary mirrors ``immigration_partner_adapter.MilestoneStatus``; the terminal
  statuses ('completed', 'not_applicable') are never flagged.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

from sqlalchemy import text

from ...database import db

logger = logging.getLogger(__name__)

# Days a milestone may sit past its target_date before it is flagged as behind.
DEFAULT_WARN_DAYS = 3
ENV_WARN_DAYS = "CASE_DELAY_WARN_DAYS"

# Days past target_date at which a delay escalates from 'warning' to 'critical'.
DEFAULT_CRIT_DAYS = 7
ENV_CRIT_DAYS = "CASE_DELAY_CRIT_DAYS"

_ACTIVE_STATUS = "active"
# Milestone statuses that mean "done" or "doesn't apply" — never flagged.
_TERMINAL_STATUSES = frozenset({"completed", "not_applicable"})
_MAX_DAYS = 3650  # clamp env thresholds to a sane upper bound


def _load_int(env_key: str, default: int, source: Optional[Mapping[str, str]] = None) -> int:
    src = os.environ if source is None else source
    raw = src.get(env_key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        val = int(float(raw))
    except (TypeError, ValueError):
        logger.warning("case_delay_monitor: %s=%r is not an int; using default %d", env_key, raw, default)
        return default
    if val < 0:
        return 0
    return min(val, _MAX_DAYS)


def load_warn_days(source: Optional[Mapping[str, str]] = None) -> int:
    """Days-late threshold before a milestone is flagged (env, clamped to [0, 3650])."""
    return _load_int(ENV_WARN_DAYS, DEFAULT_WARN_DAYS, source)


def load_crit_days(source: Optional[Mapping[str, str]] = None) -> int:
    """Critical-severity threshold, clamped to be >= the warn threshold."""
    return max(_load_int(ENV_CRIT_DAYS, DEFAULT_CRIT_DAYS, source), load_warn_days(source))


def _coerce_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class DelaySignal:
    case_id: str
    stage: str            # milestone_type of the most-overdue incomplete milestone
    expected_date: str    # ISO date string (target_date)
    days_behind: int
    severity: str         # 'warning' | 'critical'

    def as_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "stage": self.stage,
            "expected_date": self.expected_date,
            "days_behind": self.days_behind,
            "severity": self.severity,
        }


def evaluate_case_delays(
    milestones: Sequence[Mapping[str, Any]],
    *,
    now: Optional[date] = None,
    warn_days: Optional[int] = None,
    crit_days: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Pure aggregation core — no DB; ``now`` injectable for tests.

    Args:
        milestones: rows with ``case_id``, ``milestone_type``, ``status``,
            ``target_date`` (date|str|None), ``completed_date`` (date|str|None).
        now: reference date (defaults to UTC today).
        warn_days / crit_days: thresholds (default to env / clamped).

    A milestone is *behind* when it is non-terminal, not completed, has a real
    ``target_date``, and ``(today - target_date).days >= warn_days``. Returns one
    signal per case — its most-overdue behind milestone — sorted most-behind
    first. Cases with no behind milestone are omitted; ``[]`` for empty input.
    """
    today = now or datetime.now(timezone.utc).date()
    warn = load_warn_days() if warn_days is None else max(0, int(warn_days))
    crit = load_crit_days() if crit_days is None else max(int(crit_days), warn)

    worst: Dict[str, DelaySignal] = {}
    for milestone in milestones:
        status_val = str(milestone.get("status") or "").strip().lower()
        if status_val in _TERMINAL_STATUSES:
            continue
        if milestone.get("completed_date") is not None:
            continue
        target = _coerce_date(milestone.get("target_date"))
        if target is None:
            continue  # honest signals only — never flag a milestone with no ETA
        days_behind = (today - target).days
        if days_behind < warn:
            continue
        case_id = str(milestone.get("case_id") or "")
        if not case_id:
            continue
        signal = DelaySignal(
            case_id=case_id,
            stage=str(milestone.get("milestone_type") or ""),
            expected_date=target.isoformat(),
            days_behind=days_behind,
            severity="critical" if days_behind >= crit else "warning",
        )
        existing = worst.get(case_id)
        if existing is None or signal.days_behind > existing.days_behind:
            worst[case_id] = signal

    ordered = sorted(worst.values(), key=lambda s: (-s.days_behind, s.case_id))
    return [s.as_dict() for s in ordered]


# One row per incomplete, dated milestone on an active case. The threshold +
# worst-per-case reduction happen in the pure core for testability.
_ACTIVE_MILESTONES_SQL = """
SELECT m.case_id        AS case_id,
       m.milestone_type AS milestone_type,
       m.status         AS status,
       m.target_date    AS target_date,
       m.completed_date AS completed_date
FROM public.immigration_milestones m
JOIN public.relocation_cases rc ON rc.id::text = m.case_id
WHERE rc.status = :active_status
  AND m.target_date IS NOT NULL
  AND m.completed_date IS NULL
  AND COALESCE(m.status, '') NOT IN ('completed', 'not_applicable')
"""


def _fetch_active_case_milestones() -> List[Dict[str, Any]]:
    """Incomplete, dated milestones for active cases. Safe-fails to ``[]`` so a
    query error degrades to "no signal" rather than raising to the caller."""
    try:
        with db.engine.connect() as conn:
            rows = (
                conn.execute(text(_ACTIVE_MILESTONES_SQL), {"active_status": _ACTIVE_STATUS})
                .mappings()
                .all()
            )
        return [dict(r) for r in rows]
    except Exception:  # noqa: BLE001 — degrade rather than raise
        logger.exception("case_delay_monitor: fetch failed; treating as no data")
        return []


def scan_active_cases(now: Optional[date] = None) -> List[Dict[str, Any]]:
    """Read-only entry point. Returns one delay signal
    ``{case_id, stage, expected_date, days_behind, severity}`` per active
    immigration case whose most-overdue incomplete milestone is past its
    ``target_date`` by at least ``CASE_DELAY_WARN_DAYS``.

    Inert by construction: ``[]`` when there are no active cases or no overdue
    milestones (i.e. always, until the pilot populates ``immigration_milestones``).
    """
    return evaluate_case_delays(_fetch_active_case_milestones(), now=now)
