"""Correction analytics — AIQ-554 / C2-03.

Turns the rce.corrections audit log into a labelled-data signal: weekly counts
of human corrections grouped by reason_code, case_corridor, and clause_type.

This feeds the /admin/corrections/by-reason endpoint and (optionally) a weekly
Cowork digest. Scoping rules (enforced at the router layer):

  * HR caller  → restricted to their own employer (``employer_id`` set).
  * Admin      → may pass ``employer_id=None`` to see every employer.

Grouping dimensions:
  * ``week_start``  — Monday of the ISO week of ``corrected_at`` (UTC).
  * ``reason_code`` — the locked 6-value taxonomy.
  * ``case_corridor`` — ``rce.cases.corridor_id`` joined via ``case_id``.
  * ``clause_type`` — pulled from the correction's ``context_snapshot`` JSONB
    (``context_snapshot->>'clause_type'``); NULL when not present.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ...database import db

# The locked taxonomy (mirrors the C1-01 CHECK constraint). Kept here so the
# digest / analytics layer can render a stable, zero-filled set of buckets even
# in weeks where a reason never occurred.
REASON_CODES: tuple[str, ...] = (
    "OCR_ERROR",
    "TYPO_IN_SOURCE",
    "AMBIGUOUS_PARTICLE",
    "LEGITIMATE_VARIATION",
    "FRAUD_SUSPECTED",
    "OTHER",
)


def _week_start_utc(now: Optional[datetime] = None) -> datetime:
    """Monday 00:00:00 UTC of the current ISO week."""
    now = now or datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def weekly_corrections_by_reason(
    employer_id: Optional[str] = None,
    weeks_back: int = 4,
) -> List[Dict[str, Any]]:
    """Weekly correction counts grouped by reason_code, corridor, and clause_type.

    Returns a flat list of rows::

        [
          {
            "week_start": "2026-05-25",
            "reason_code": "OCR_ERROR",
            "case_corridor": "IN-DE",
            "clause_type": "housing_allowance",
            "count": 3,
          },
          ...
        ]

    ``employer_id=None`` aggregates across all employers (admin override).
    """
    weeks_back = max(1, min(int(weeks_back or 4), 52))
    window_start = _week_start_utc() - timedelta(weeks=weeks_back - 1)

    # date_trunc('week', ...) yields the Monday of the week in Postgres.
    sql = """
        SELECT
            date_trunc('week', co.corrected_at) AS week_start,
            co.reason_code                       AS reason_code,
            ca.corridor_id                       AS case_corridor,
            (co.context_snapshot->>'clause_type') AS clause_type,
            COUNT(*)                             AS count
        FROM rce.corrections AS co
        LEFT JOIN rce.cases AS ca ON ca.case_id = co.case_id
        WHERE co.corrected_at >= :window_start
          AND (:employer_id IS NULL OR ca.employer_id = CAST(:employer_id AS uuid))
        GROUP BY 1, 2, 3, 4
        ORDER BY 1 DESC, 2 ASC
    """

    rows: List[Dict[str, Any]] = []
    with db.engine.begin() as conn:
        result = conn.execute(
            text(sql),
            {"window_start": window_start, "employer_id": employer_id},
        ).mappings().all()

    for r in result:
        ws = r["week_start"]
        if hasattr(ws, "date"):
            week_start = ws.date().isoformat()
        elif hasattr(ws, "isoformat"):
            week_start = ws.isoformat()
        else:
            # SQLite returns a string from date_trunc shim; take the date prefix.
            week_start = str(ws)[:10]
        rows.append(
            {
                "week_start": week_start,
                "reason_code": r["reason_code"],
                "case_corridor": r["case_corridor"],
                "clause_type": r["clause_type"],
                "count": int(r["count"]),
            }
        )
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# AIQ-871: group_by-aware pivoted counts for the AIQ-598 trend dashboard.
# ─────────────────────────────────────────────────────────────────────────────

GROUP_BY_DIMENSIONS: tuple[str, ...] = ("reason", "agent", "corridor", "clause_type")

# SQL expression per dimension. 'agent' = the extracting AI agent recorded in the
# correction's context_snapshot (the same JSONB the clause_type dimension reads).
# rce.corrections has no dedicated agent column; context_snapshot->>'agent' is the
# canonical source once the C1-12 Resolution UI logs it. NULL → 'unknown' bucket.
_GROUP_BY_SQL: Dict[str, str] = {
    "reason": "co.reason_code",
    "agent": "(co.context_snapshot->>'agent')",
    "corridor": "ca.corridor_id",
    "clause_type": "(co.context_snapshot->>'clause_type')",
}


def weekly_correction_counts(
    employer_id: Optional[str] = None,
    group_by: str = "reason",
    weeks_back: int = 4,
) -> Dict[str, Any]:
    """Weekly correction counts pivoted by one dimension (AIQ-871).

    Returns the exact shape the AIQ-598 trend dashboard consumes::

        {
          "buckets": [{"week_start": "2026-05-25", "counts": {"OCR_ERROR": 3, ...}}, ...],
          "series":  ["OCR_ERROR", ...],   # distinct dimension values, stable order
          "group_by": "reason",
        }

    ``group_by`` is one of ``GROUP_BY_DIMENSIONS`` (unknown falls back to
    ``reason``). A NULL dimension value is bucketed under ``'unknown'``. Same
    tenant scoping + ISO-week window as ``weekly_corrections_by_reason``.
    """
    if group_by not in _GROUP_BY_SQL:
        group_by = "reason"
    dim_expr = _GROUP_BY_SQL[group_by]
    weeks_back = max(1, min(int(weeks_back or 4), 52))
    window_start = _week_start_utc() - timedelta(weeks=weeks_back - 1)

    sql = f"""
        SELECT
            date_trunc('week', co.corrected_at) AS week_start,
            COALESCE({dim_expr}, 'unknown')      AS dim_value,
            COUNT(*)                             AS count
        FROM rce.corrections AS co
        LEFT JOIN rce.cases AS ca ON ca.case_id = co.case_id
        WHERE co.corrected_at >= :window_start
          AND (:employer_id IS NULL OR ca.employer_id = CAST(:employer_id AS uuid))
        GROUP BY 1, 2
        ORDER BY 1 ASC
    """
    with db.engine.begin() as conn:
        result = conn.execute(
            text(sql), {"window_start": window_start, "employer_id": employer_id}
        ).mappings().all()

    by_week: Dict[str, Dict[str, int]] = {}
    series: set = set()
    for r in result:
        ws = r["week_start"]
        if hasattr(ws, "date"):
            wk = ws.date().isoformat()
        elif hasattr(ws, "isoformat"):
            wk = ws.isoformat()
        else:
            wk = str(ws)[:10]
        val = str(r["dim_value"])
        series.add(val)
        by_week.setdefault(wk, {})[val] = int(r["count"])

    buckets = [{"week_start": wk, "counts": by_week[wk]} for wk in sorted(by_week)]
    return {"buckets": buckets, "series": sorted(series), "group_by": group_by}


def summarize_by_reason(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """Collapse the grouped rows into a total-per-reason map, zero-filled.

    Used by the weekly digest so a week with 0 corrections still renders every
    reason at 0 (validation criterion 5).
    """
    totals: Dict[str, int] = {code: 0 for code in REASON_CODES}
    for r in rows:
        code = r.get("reason_code")
        if code in totals:
            totals[code] += int(r.get("count") or 0)
        else:
            # Defensive: an out-of-taxonomy code would indicate enum drift.
            totals[code] = totals.get(code, 0) + int(r.get("count") or 0)
    return totals
