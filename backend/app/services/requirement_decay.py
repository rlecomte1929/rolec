"""RP-MEM-002 — catalog decay labels for `requirement_items.last_verified_at`.

Stale means "due for human re-verification", not "un-approve". Serving still
filters on `review_status=approved` only (`requirements_builder`,
`crud.list_requirements`). This module never writes that column.

Cycle days are code-side, keyed by pillar. No new public column.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional, Sequence

# Immigration / residence move faster; housing / healthcare / everything else
# is treated as structural (annual review). Unknown pillars use the structural
# default so a new catalog label is not silently unmonitored.
PILLAR_CYCLE_DAYS = {
    "IMMIGRATION": 90,
    "RESIDENCE": 90,
    "HOUSING": 365,
    "HEALTHCARE": 365,
}
DEFAULT_CYCLE_DAYS = 365


def cycle_days_for(pillar: Optional[str]) -> int:
    key = (pillar or "").strip().upper()
    return PILLAR_CYCLE_DAYS.get(key, DEFAULT_CYCLE_DAYS)


def _as_naive_utc(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
    else:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def age_days(now: datetime, last_verified_at: Any) -> Optional[int]:
    verified = _as_naive_utc(last_verified_at)
    clock = _as_naive_utc(now)
    if verified is None or clock is None:
        return None
    return (clock - verified).days


def is_stale(now: datetime, row: Any) -> bool:
    """True when `last_verified_at` is at least one full cycle old for the pillar."""
    days = age_days(now, getattr(row, "last_verified_at", None))
    if days is None:
        return False
    return days >= cycle_days_for(getattr(row, "pillar", None))


def stale_approved_rows(rows: Iterable[Any], now: datetime) -> List[Any]:
    out: List[Any] = []
    for row in rows:
        status = getattr(row, "review_status", None) or "approved"
        if status != "approved":
            continue
        if is_stale(now, row):
            out.append(row)
    return out


def format_decay_report(rows: Sequence[Any], now: datetime) -> str:
    """One line per stale approved row: country_code, id, title, age_days, cycle_days."""
    lines = []
    for row in stale_approved_rows(rows, now):
        country = getattr(row, "country_code", "") or ""
        rid = getattr(row, "id", "") or ""
        title = getattr(row, "title", "") or ""
        days = age_days(now, getattr(row, "last_verified_at", None))
        cycle = cycle_days_for(getattr(row, "pillar", None))
        lines.append(f"{country}\t{rid}\t{title}\t{days}\t{cycle}")
    return "\n".join(lines) + ("\n" if lines else "")
