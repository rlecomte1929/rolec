"""6-month-before-end repatriation planning sweep.

Seeds the Engine B ``return`` phase onto temporary assignments when today falls
in ``[assignment_end - 182d, assignment_end)``. Standalone repatriation cases
already get the phase at submit via ``compute_default_milestones``.

Two layers, split so the decision half needs no database:

* :func:`plan_case` — pure: a case dict + injected ``today`` in, seed-or-skip out.
* :func:`run_repatriation_planning_sweep` — DB: fetch open cases, skip if any
  return milestone already exists, append-only insert, optional case_events
  marker. ``dry_run`` writes nothing.

Never guesses an end date. Missing start or duration is a stated skip, never
defaulted to today. No LLM imports.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Set

from sqlalchemy import bindparam, text as _sql_text

from .timeline_service import (
    build_return_milestones,
    derive_assignment_end_date,
    parse_assignment_start_from_draft,
    parse_expected_duration_months,
    _parse_date_value,
)

log = logging.getLogger(__name__)

WINDOW_DAYS = 182
EVENT_TYPE = "repatriation.planning_seeded"
_ACTIVE_PUBLIC_STATUSES = ("active", "on_hold", "draft")
_PERMANENT_TYPES = frozenset({"PERMANENT", "permanent_transfer", "permanent"})
_DOMESTIC_TYPES = frozenset({"domestic_move", "domestic"})


@dataclass
class CasePlanResult:
    case_ref: str
    skip_reason: Optional[str] = None
    end_date: Optional[date] = None


def _main_db():
    from ...database import db  # type: ignore[import]
    return db


def _engine():
    return _main_db().engine


def _t(name: str) -> str:
    try:
        dialect = _engine().dialect.name
    except Exception:
        dialect = "sqlite"
    return f"public.{name}" if dialect == "postgresql" else name


def _as_date(value: Any) -> Optional[date]:
    return _parse_date_value(value)


def _norm_type(value: Any) -> str:
    return str(value or "").strip()


def _is_permanent(case: Dict[str, Any]) -> bool:
    at = _norm_type(case.get("assignment_type")).upper()
    ct = _norm_type(case.get("contract_type")).lower()
    if at == "PERMANENT" or ct in _PERMANENT_TYPES:
        return True
    return False


def _is_domestic(case: Dict[str, Any]) -> bool:
    ct = _norm_type(case.get("contract_type")).lower()
    at = _norm_type(case.get("assignment_type")).lower()
    if ct in _DOMESTIC_TYPES or at == "domestic":
        return True
    origin = _norm_type(case.get("origin_country_code")).upper()
    dest = _norm_type(case.get("dest_country_code")).upper()
    return bool(origin and dest and origin == dest)


def _end_date_for_case(case: Dict[str, Any]) -> Optional[date]:
    stored = _as_date(case.get("assignment_end_date"))
    if stored is not None:
        return stored
    start = _as_date(case.get("assignment_start_date")) or _as_date(case.get("target_move_date"))
    months = case.get("expected_duration_months")
    try:
        months_i = int(months) if months is not None and str(months).strip() != "" else None
    except (TypeError, ValueError):
        months_i = None
    draft = case.get("draft") or {}
    if start is None:
        start = parse_assignment_start_from_draft(draft)
    if months_i is None:
        months_i = parse_expected_duration_months(draft)
    return derive_assignment_end_date(start, months_i)


def plan_case(
    case: Dict[str, Any],
    *,
    today: date,
    already_seeded: bool = False,
) -> CasePlanResult:
    """Whether this case should receive return tasks today, or why not.

    ``today`` is injected, never read from the clock.
    """
    case_ref = str(case.get("id") or "")
    if already_seeded:
        return CasePlanResult(case_ref=case_ref, skip_reason="already_seeded")
    if _is_permanent(case):
        return CasePlanResult(case_ref=case_ref, skip_reason="permanent")
    if _is_domestic(case):
        return CasePlanResult(case_ref=case_ref, skip_reason="domestic")
    end = _end_date_for_case(case)
    if end is None:
        return CasePlanResult(case_ref=case_ref, skip_reason="missing_end_date")
    window_open = end - timedelta(days=WINDOW_DAYS)
    if today < window_open or today >= end:
        return CasePlanResult(case_ref=case_ref, skip_reason="outside_window", end_date=end)
    return CasePlanResult(case_ref=case_ref, end_date=end)


# ─────────────────────────────────────────────────────────────────────────────
# Database layer
# ─────────────────────────────────────────────────────────────────────────────


def _fetch_open_cases() -> List[Dict[str, Any]]:
    sql = f"""
        SELECT c.id, c.origin_country_code, c.dest_country_code,
               c.target_move_date, c.status, c.assignment_type,
               c.expected_duration_months, c.assignment_end_date
        FROM {_t('cases')} c
        WHERE lower(coalesce(c.status,'')) IN ('active', 'on_hold', 'draft')
        ORDER BY c.created_at
    """
    try:
        with _engine().connect() as conn:
            return [dict(r) for r in conn.execute(_sql_text(sql)).mappings().all()]
    except Exception as exc:  # noqa: BLE001
        log.error("repatriation_planning_sweep: case fetch failed: %s", exc)
        return []


def _seeded_case_ids(case_ids: Sequence[str]) -> Set[str]:
    """Cases that already have at least one return milestone. Fail closed."""
    if not case_ids:
        return set()
    try:
        with _engine().connect() as conn:
            stmt = _sql_text(
                f"SELECT DISTINCT case_id FROM {_t('case_milestones')} "
                "WHERE case_id IN :ids AND milestone_type LIKE 'task_return_%'"
            ).bindparams(bindparam("ids", expanding=True))
            rows = conn.execute(stmt, {"ids": list(case_ids)}).mappings().all()
        return {str(r["case_id"]) for r in rows}
    except Exception as exc:  # noqa: BLE001
        log.error("repatriation_planning_sweep: ledger read failed, suppressing: %s", exc)
        return set(case_ids)


def _insert_return_milestones(conn, case_id: str, rows: List[Dict[str, Any]], today: date) -> int:
    written = 0
    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        mid = str(uuid.uuid4())
        conn.execute(
            _sql_text(
                f"INSERT INTO {_t('case_milestones')} "
                "(id, case_id, canonical_case_id, milestone_type, title, description, "
                "target_date, status, sort_order, created_at, updated_at, owner, "
                "criticality, notes) "
                "VALUES (:id, :cid, :canonical, :mt, :title, :desc, :td, :status, "
                ":so, :now, :now, :owner, :crit, :notes)"
            ),
            {
                "id": mid,
                "cid": case_id,
                "canonical": case_id,
                "mt": row["milestone_type"],
                "title": row["title"],
                "desc": row.get("description"),
                "td": row.get("target_date"),
                "status": row.get("status") or "pending",
                "so": row.get("sort_order") or 0,
                "now": now,
                "owner": row.get("owner") or "joint",
                "crit": row.get("criticality") or "normal",
                "notes": json.dumps({"seeded_on": today.isoformat(), "source": EVENT_TYPE}),
            },
        )
        written += 1
    return written


def _insert_seeded_event(conn, case_id: str, today: date) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        _sql_text(
            f"INSERT INTO {_t('case_events')} "
            "(id, case_id, canonical_case_id, event_type, payload, created_at) "
            "VALUES (:id, :cid, :canonical, :et, :pl, :ca)"
        ),
        {
            "id": str(uuid.uuid4()),
            "cid": case_id,
            "canonical": case_id,
            "et": EVENT_TYPE,
            "pl": json.dumps({"seeded_on": today.isoformat()}),
            "ca": now,
        },
    )


def run_repatriation_planning_sweep(
    *,
    today: Optional[date] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    cases = _fetch_open_cases()
    seeded = set() if dry_run else _seeded_case_ids([str(c.get("id")) for c in cases if c.get("id")])

    results: List[CasePlanResult] = []
    for case in cases:
        cid = str(case.get("id") or "")
        try:
            results.append(
                plan_case(case, today=today, already_seeded=cid in seeded)
            )
        except Exception as exc:  # noqa: BLE001
            log.error("repatriation_planning_sweep: plan failed for case %s: %s", cid, exc)
            results.append(CasePlanResult(case_ref=cid, skip_reason=f"planning error: {exc}"))

    skipped = [r for r in results if r.skip_reason]
    to_seed = [r for r in results if not r.skip_reason]
    by_id = {str(c.get("id")): c for c in cases}

    summary: Dict[str, Any] = {
        "today": today.isoformat(),
        "dry_run": dry_run,
        "cases_scanned": len(cases),
        "cases_skipped": len(skipped),
        "seeded": 0,
        "errors": 0,
        "skips": [{"case_ref": r.case_ref, "reason": r.skip_reason} for r in skipped],
        "would_seed" if dry_run else "seeded_cases": [],
    }
    key = "would_seed" if dry_run else "seeded_cases"

    for result in to_seed:
        entry = {"case_ref": result.case_ref, "end_date": result.end_date.isoformat() if result.end_date else None}
        if dry_run:
            summary[key].append(entry)
            continue
        try:
            rows = build_return_milestones(result.end_date)
            with _engine().begin() as conn:
                written = _insert_return_milestones(conn, result.case_ref, rows, today)
            try:
                with _engine().begin() as conn:
                    _insert_seeded_event(conn, result.case_ref, today)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "repatriation_planning_sweep: case_events marker failed %s: %s",
                    result.case_ref, exc,
                )
            entry["milestones"] = written
            summary[key].append(entry)
            summary["seeded"] += 1
        except Exception as exc:  # noqa: BLE001
            log.error("repatriation_planning_sweep: insert failed %s: %s", result.case_ref, exc)
            summary["errors"] += 1
            summary["skips"].append({"case_ref": result.case_ref, "reason": f"insert error: {exc}"})

    log.info(
        "repatriation_planning_sweep: today=%s dry_run=%s cases=%d skipped=%d seeded=%d errors=%d",
        today, dry_run, len(cases), len(skipped), summary["seeded"], summary["errors"],
    )
    _ = by_id
    return summary
