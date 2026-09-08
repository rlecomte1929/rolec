"""
Controlled requirement evaluation for a live assignment (admin / internal).

Resolves mobility_cases.id from assignment_mobility_links, runs RequirementEvaluationService,
then NextActionService preview. Does not run automatically on employee flows.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from .next_action_service import NextActionService
from .requirement_evaluation_service import RequirementEvaluationService

log = logging.getLogger(__name__)


def _count_by_status(results: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for r in results:
        st = (r.get("evaluation_status") or "unknown").strip() or "unknown"
        counts[st] = counts.get(st, 0) + 1
    return counts


def run_evaluation_for_assignment(
    db: Any,
    assignment_id: str,
) -> Dict[str, Any]:
    """
    Run graph requirement evaluation for the mobility case linked to assignment_id.

    Returns a dict with ok=True and payloads, or ok=False and error (caller maps to HTTP).
    """
    aid = (assignment_id or "").strip()
    if not aid:
        return {
            "ok": False,
            "error": {"code": "invalid_assignment_id", "message": "assignment_id is required"},
        }

    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT mobility_case_id FROM assignment_mobility_links "
                    "WHERE assignment_id = :aid LIMIT 1"
                ),
                {"aid": aid},
            ).mappings().first()
    except (ProgrammingError, OperationalError) as ex:
        log.warning("run_evaluation_for_assignment: bridge unreadable: %s", ex)
        return {
            "ok": False,
            "error": {
                "code": "schema_unavailable",
                "message": "assignment_mobility_links or mobility graph not available",
            },
        }

    if not row or row.get("mobility_case_id") is None:
        return {
            "ok": False,
            "assignment_id": aid,
            "error": {
                "code": "no_mobility_link",
                "message": "No mobility case linked to this assignment; ensure bridge sync ran.",
            },
        }

    mid = str(row["mobility_case_id"]).strip()
    if not mid:
        return {
            "ok": False,
            "assignment_id": aid,
            "error": {"code": "no_mobility_link", "message": "Linked mobility_case_id is empty."},
        }

    with db.engine.begin() as conn:
        ev = RequirementEvaluationService().evaluate_case(conn, mid)

    err = ev.get("error")
    if err:
        code = (err.get("code") or "").strip()
        log.info(
            "admin.evaluate_assignment assignment_id=%s mobility_case_id=%s evaluation_error=%s",
            aid,
            mid,
            code,
        )
        return {
            "ok": False,
            "assignment_id": aid,
            "mobility_case_id": mid,
            "error": err,
        }

    results: List[Dict[str, Any]] = list(ev.get("results") or [])
    meta = ev.get("meta") or {}
    evaluated_count = int(meta.get("evaluated_count") or len(results))

    with db.engine.connect() as conn:
        next_payload = NextActionService().list_actions(conn, mid)

    log.info(
        "admin.evaluate_assignment assignment_id=%s mobility_case_id=%s evaluated_count=%s next_action_count=%s",
        aid,
        mid,
        evaluated_count,
        (next_payload.get("meta") or {}).get("action_count"),
    )

    summary = [
        {
            "requirement_code": r.get("requirement_code"),
            "evaluation_status": r.get("evaluation_status"),
            "source_rule_code": r.get("source_rule_code"),
            "evaluation_id": r.get("evaluation_id"),
        }
        for r in results
    ]

    return {
        "ok": True,
        "assignment_id": aid,
        "mobility_case_id": mid,
        "evaluated_at": meta.get("evaluated_at"),
        "evaluated_by": meta.get("evaluated_by"),
        "evaluated_count": evaluated_count,
        "status_counts": _count_by_status(results),
        "results": summary,
        "next_actions_preview": {
            "meta": next_payload.get("meta") or {},
            "actions": next_payload.get("actions") or [],
        },
    }
