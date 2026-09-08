"""P2-01c — >30-day source-staleness warning on roadmap steps.

A shown roadmap step whose cited source was last updated more than
STALENESS_THRESHOLD_DAYS (30) days ago is annotated with a `staleness_warning`,
and the roadmap is stamped with a top-level `has_stale_sources`. The source age
is taken from the oldest available timestamp on the step (`source_updated_at` or
any `citations[].updated_at`); when no parseable timestamp is present the step
never warns (fail-open on missing data, so it cannot false-fire before the
pipeline propagates source timestamps).

`now` is always injected so the comparison core is wall-clock-free and testable.
This is the flat 30-day rule for roadmap citations — distinct from
freshness_service, which tracks cadence-based crawl freshness for live country
resources.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

STALENESS_THRESHOLD_DAYS = 30


def _as_utc(now: _dt.datetime) -> _dt.datetime:
    return now if now.tzinfo is not None else now.replace(tzinfo=_dt.timezone.utc)


def _parse(ts: Any) -> Optional[_dt.datetime]:
    if not ts:
        return None
    if isinstance(ts, _dt.datetime):
        dt = ts
    elif isinstance(ts, _dt.date):
        dt = _dt.datetime(ts.year, ts.month, ts.day)
    else:
        try:
            dt = _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=_dt.timezone.utc)


def _age_days(ts: _dt.datetime, now: _dt.datetime) -> int:
    return (_as_utc(now) - ts).days


def is_source_stale(
    ts: Any, *, now: _dt.datetime, threshold_days: int = STALENESS_THRESHOLD_DAYS
) -> bool:
    """True iff `ts` parses to a date more than `threshold_days` days before `now`.
    Absent / unparseable timestamps are not stale."""
    dt = _parse(ts)
    if dt is None:
        return False
    return _age_days(dt, now) > threshold_days


def _step_timestamps(step: Dict[str, Any]) -> List[_dt.datetime]:
    out: List[_dt.datetime] = []
    primary = _parse(step.get("source_updated_at"))
    if primary:
        out.append(primary)
    for citation in step.get("citations") or []:
        ts = _parse((citation or {}).get("updated_at"))
        if ts:
            out.append(ts)
    return out


def annotate_staleness(
    roadmap: Dict[str, Any],
    *,
    now: _dt.datetime,
    threshold_days: int = STALENESS_THRESHOLD_DAYS,
) -> Dict[str, Any]:
    """Return a copy of `roadmap` with a `staleness_warning` on each shown step
    whose oldest cited source exceeds the threshold, plus a top-level
    `has_stale_sources`. Does not mutate the input."""
    now = _as_utc(now)
    annotated: List[Dict[str, Any]] = []
    any_stale = False
    for step in roadmap.get("steps") or []:
        s = dict(step)
        timestamps = _step_timestamps(step)
        if timestamps:
            oldest = min(timestamps)  # oldest timestamp == greatest age
            age = _age_days(oldest, now)
            if age > threshold_days:
                any_stale = True
                s["staleness_warning"] = {
                    "stale": True,
                    "age_days": age,
                    "threshold_days": threshold_days,
                    "source_updated_at": oldest.date().isoformat(),
                }
        annotated.append(s)

    out = dict(roadmap)
    out["steps"] = annotated
    out["has_stale_sources"] = any_stale
    return out
