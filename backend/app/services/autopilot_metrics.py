"""autopilot_metrics.py — Phase 4: read the autopilot funnel + cost for the admin dashboard.

Funnel: occurrence counts per `autopilot.*` event_type in `public.events` (+ dedup raw/unique
pulled from the run events' properties). Cost: month-to-date autopilot spend per stage from
`policy_assistant_traces` vs the monthly ceiling. All queries are fail-soft (return zeros if a
table is absent, e.g. the SQLite test DB) — the dashboard degrades to an honest-empty state
rather than 500-ing, mirroring `ai_unit_economics`.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy import text

from ..db import SessionLocal
from . import autopilot_events as ev
from .autopilot_governor import FEATURE_KEY_PREFIX, monthly_cap_usd

log = logging.getLogger(__name__)


def _parse_props(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def _funnel_counts(s: Any, since: Optional[str]) -> Dict[str, int]:
    where = "event_type LIKE :pfx"
    params: Dict[str, Any] = {"pfx": "autopilot.%"}
    if since:
        where += " AND created_at >= :since"
        params["since"] = since
    try:
        rows = s.execute(
            text(f"SELECT event_type, COUNT(*) FROM events WHERE {where} GROUP BY event_type"),
            params,
        ).fetchall()
        return {r[0]: int(r[1] or 0) for r in rows}
    except Exception:
        log.debug("autopilot_metrics funnel query failed", exc_info=True)
        return {}


def _dedup_totals(s: Any, since: Optional[str]) -> Dict[str, Any]:
    """Sum raw vs unique from the ingest/dedup run events' properties (portable — done in Python)."""
    where = "event_type IN (:ing, :ded)"
    params: Dict[str, Any] = {"ing": ev.FEEDBACK_INGESTED, "ded": ev.FEEDBACK_DEDUPED}
    if since:
        where += " AND created_at >= :since"
        params["since"] = since
    raw_total = unique_total = 0
    try:
        rows = s.execute(text(f"SELECT event_type, properties FROM events WHERE {where}"), params).fetchall()
        for et, props in rows:
            p = _parse_props(props)
            if et == ev.FEEDBACK_DEDUPED:
                raw_total += int(p.get("raw") or 0)
                unique_total += int(p.get("unique") or 0)
    except Exception:
        log.debug("autopilot_metrics dedup query failed", exc_info=True)
    factor = round(raw_total / unique_total, 2) if unique_total else None
    return {"raw": raw_total, "unique": unique_total, "dedup_factor": factor}


def _cost_by_stage(s: Any, since: Optional[str]) -> Dict[str, Any]:
    where = "feature_key LIKE :pfx"
    params: Dict[str, Any] = {"pfx": f"{FEATURE_KEY_PREFIX}%"}
    if since:
        where += " AND created_at >= :since"
        params["since"] = since
    stages = []
    total = 0.0
    try:
        rows = s.execute(
            text(
                f"SELECT feature_key, COALESCE(SUM(cost_usd_estimated),0), COUNT(*), "
                f"COALESCE(SUM(tokens_in),0), COALESCE(SUM(tokens_out),0) "
                f"FROM policy_assistant_traces WHERE {where} GROUP BY feature_key"
            ),
            params,
        ).fetchall()
        for r in rows:
            cost = float(r[1] or 0.0)
            total += cost
            stages.append({"stage": r[0], "cost_usd": round(cost, 6), "n_calls": int(r[2] or 0),
                           "tokens_in": int(r[3] or 0), "tokens_out": int(r[4] or 0)})
    except Exception:
        log.debug("autopilot_metrics cost query failed", exc_info=True)
    return {"by_stage": stages, "total_usd": round(total, 6)}


def compute_autopilot_metrics(*, since: Optional[str] = None, session: Any = None) -> Dict[str, Any]:
    """Funnel + cost + derived KPIs for the autopilot dashboard. `since` = inclusive ISO-8601
    lower bound on created_at (both events + traces are stored as comparable timestamps/text)."""
    own = session is None
    s = session or SessionLocal()
    try:
        funnel = _funnel_counts(s, since)
        dedup = _dedup_totals(s, since)
        cost = _cost_by_stage(s, since)
    finally:
        if own:
            s.close()

    def c(name: str) -> int:
        return int(funnel.get(name, 0))

    canary_pass = c(ev.CANARY_PASSED)
    canary_total = canary_pass + c(ev.CANARY_FAILED)
    merged = c(ev.MERGED)
    cap = monthly_cap_usd()

    kpis = {
        "dedup_factor": dedup["dedup_factor"],
        "tasks_dispatched": c(ev.TASK_DISPATCHED),
        "merged": merged,
        "tasks_done": c(ev.TASK_DONE),
        "reverted": c(ev.REVERTED),
        "escalated_to_human": c(ev.ESCALATED_TO_HUMAN),
        "runs_halted": c(ev.RUN_HALTED),
        "canary_pass_rate": round(canary_pass / canary_total, 3) if canary_total else None,
        "revert_rate": round(c(ev.REVERTED) / merged, 3) if merged else None,
    }
    return {
        "since": since,
        "funnel": funnel,
        "dedup": dedup,
        "cost": {**cost, "monthly_cap_usd": cap, "remaining_usd": round(max(0.0, cap - cost["total_usd"]), 6)},
        "kpis": kpis,
    }


def write_daily_digest(*, day: str, session: Any = None) -> Dict[str, Any]:
    """Upsert one `daily_summaries` row summarising the day's autopilot funnel + cost. Fail-soft:
    if the table is absent (e.g. SQLite dev) the summary is still returned, just not persisted."""
    m = compute_autopilot_metrics(since=day, session=session)
    k, d, cost = m["kpis"], m["dedup"], m["cost"]
    summary = (
        f"Autopilot {day}: dispatched {k['tasks_dispatched']}, merged {k['merged']}, "
        f"done {k['tasks_done']}, reverted {k['reverted']}, dedup {d['dedup_factor']}, "
        f"${cost['total_usd']:.2f} spent."
    )
    counts = {"funnel": m["funnel"], "kpis": k, "cost_total_usd": cost["total_usd"]}
    own = session is None
    s = session or SessionLocal()
    persisted = False
    try:
        s.execute(
            text(
                "INSERT INTO daily_summaries (date, summary_type, summary_text, raw_counts) "
                "VALUES (:d, 'platform_health', :t, CAST(:rc AS jsonb)) "
                "ON CONFLICT (date, summary_type) DO UPDATE SET "
                "  summary_text = excluded.summary_text, raw_counts = excluded.raw_counts"
            ),
            {"d": day, "t": summary, "rc": json.dumps(counts)},
        )
        if own:
            s.commit()
        persisted = True
    except Exception:
        log.info("autopilot digest not persisted (table absent?)", exc_info=True)
    finally:
        if own:
            s.close()
    return {"date": day, "summary": summary, "persisted": persisted}
