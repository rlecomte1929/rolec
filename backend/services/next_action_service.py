"""
NextActionService — user-friendly next steps from mobility evaluations (MVP).

Reads case_requirement_evaluations joined to requirements_catalog; surfaces
rows with status missing or needs_review. Optional spouse reminder from case metadata.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import ProgrammingError

log = logging.getLogger(__name__)


def _parse_uuid(case_id_raw: Optional[str]) -> Optional[uuid.UUID]:
    if case_id_raw is None:
        return None
    s = str(case_id_raw).strip()
    if not s:
        return None
    try:
        return uuid.UUID(s)
    except (ValueError, AttributeError):
        return None


def _coerce_json(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        t = value.strip()
        if not t:
            return {}
        try:
            out = json.loads(t)
            return dict(out) if isinstance(out, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _serialize_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)

# (requirement_code, evaluation_status) -> (priority lower = sooner, title, description)
# evaluation_status is 'missing' | 'needs_review'
_ACTION_COPY: Dict[Tuple[str, str], Tuple[int, str, str]] = {
    ("passport_copy_uploaded", "missing"): (
        1,
        "Upload a valid passport copy",
        "Add a clear copy of the passport photo page so HR can verify identity.",
    ),
    ("passport_copy_uploaded", "needs_review"): (
        2,
        "Fix or replace your passport copy",
        "The passport file needs a new upload or HR review — check the notes on your case.",
    ),
    ("passport_valid", "missing"): (
        1,
        "Upload passport documentation",
        "We need passport details on file before this step can move forward.",
    ),
    ("passport_valid", "needs_review"): (
        2,
        "Confirm passport validity",
        "A passport file is uploaded; please confirm expiry dates are current or upload an updated copy.",
    ),
    ("signed_employment_contract", "missing"): (
        3,
        "Add signed employment contract",
        "Upload the signed employment contract for this assignment.",
    ),
    ("signed_employment_contract", "needs_review"): (
        3,
        "Review employment contract",
        "The contract file needs a quick check or a fresh upload.",
    ),
    ("proof_of_address", "missing"): (
        4,
        "Add proof of address",
        "Upload a recent utility bill, lease, or bank statement showing your address.",
    ),
    ("proof_of_address", "needs_review"): (
        4,
        "Review proof of address",
        "The address document may be out of date or unclear — please upload a clearer version if asked.",
    ),
}


def _action_for_row(requirement_code: str, status: str, reason_text: Optional[str]) -> Tuple[int, str, str]:
    key = (requirement_code.strip(), status.strip())
    if key in _ACTION_COPY:
        return _ACTION_COPY[key]
    # Fallback: still show something readable
    if status == "missing":
        return (
            5,
            f"Complete: {requirement_code}",
            (reason_text or "This item is still missing for your relocation case.").strip(),
        )
    return (
        4,
        f"Review: {requirement_code}",
        (reason_text or "This item needs a quick review from you or HR.").strip(),
    )


def _fetch_open_evaluations(conn: Connection, case_id_str: str) -> List[Dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
              e.id AS evaluation_id,
              e.evaluation_status,
              e.reason_text,
              r.requirement_code
            FROM case_requirement_evaluations AS e
            INNER JOIN requirements_catalog AS r ON r.id = e.requirement_id
            WHERE e.case_id = :case_id
              AND e.evaluation_status IN ('missing', 'needs_review')
            ORDER BY r.requirement_code ASC, e.id ASC
            """
        ),
        {"case_id": case_id_str},
    ).mappings().all()
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "evaluation_id": _serialize_id(row.get("evaluation_id")),
                "evaluation_status": row.get("evaluation_status"),
                "reason_text": row.get("reason_text"),
                "requirement_code": row.get("requirement_code"),
            }
        )
    return out


def _fetch_case_and_people(conn: Connection, case_id_str: str) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    case_row = conn.execute(
        text(
            """
            SELECT id, metadata
            FROM mobility_cases
            WHERE id = :case_id
            LIMIT 1
            """
        ),
        {"case_id": case_id_str},
    ).mappings().first()
    if not case_row:
        return None, []
    case = {
        "id": _serialize_id(case_row.get("id")),
        "metadata": _coerce_json(case_row.get("metadata")),
    }
    people_rows = conn.execute(
        text(
            """
            SELECT id, role
            FROM case_people
            WHERE case_id = :case_id
            ORDER BY created_at ASC, id ASC
            """
        ),
        {"case_id": case_id_str},
    ).mappings().all()
    people: List[Dict[str, Any]] = []
    for p in people_rows:
        people.append(
            {
                "id": _serialize_id(p.get("id")),
                "role": p.get("role"),
            }
        )
    return case, people


def _spouse_household_action(case_id_str: str, case: Dict[str, Any], people: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    meta = case.get("metadata") or {}
    if not meta.get("household_includes_spouse"):
        return None
    if any((p.get("role") or "").strip() == "spouse_partner" for p in people):
        return None
    return {
        "id": f"next-household-spouse-{case_id_str}",
        "action_title": "Review spouse information",
        "action_description": (
            "Your household includes a spouse or partner for this move — add their details "
            "or confirm with HR if they are not relocating."
        ),
        "priority": 3,
        "related_requirement_code": None,
    }


class NextActionService:
    def list_actions(self, conn: Connection, case_id_raw: Optional[str]) -> Dict[str, Any]:
        uid = _parse_uuid(case_id_raw)
        base: Dict[str, Any] = {
            "meta": {
                "ok": True,
                "case_id": str(uid) if uid else None,
                "case_found": False,
                "action_count": 0,
            },
            "actions": [],
        }
        if uid is None:
            base["meta"]["ok"] = False
            base["meta"]["error"] = {"code": "invalid_case_id", "message": "case_id must be a valid UUID"}
            return base

        case_id_str = str(uid)

        try:
            case, people = _fetch_case_and_people(conn, case_id_str)
        except ProgrammingError as ex:
            log.warning("NextActionService: schema unavailable: %s", ex)
            base["meta"]["ok"] = False
            base["meta"]["error"] = {"code": "mobility_schema_unavailable", "message": str(ex)}
            return base

        if not case:
            return base

        base["meta"]["case_found"] = True

        try:
            eval_rows = _fetch_open_evaluations(conn, case_id_str)
        except ProgrammingError as ex:
            log.warning("NextActionService: evaluations query failed: %s", ex)
            base["meta"]["ok"] = False
            base["meta"]["error"] = {"code": "mobility_schema_unavailable", "message": str(ex)}
            return base

        actions: List[Dict[str, Any]] = []
        for row in eval_rows:
            code = (row.get("requirement_code") or "").strip()
            st = (row.get("evaluation_status") or "").strip()
            eid = row.get("evaluation_id")
            if not code or not st or not eid:
                continue
            pri, title, desc = _action_for_row(code, st, row.get("reason_text"))
            actions.append(
                {
                    "id": str(eid),
                    "action_title": title,
                    "action_description": desc,
                    "priority": pri,
                    "related_requirement_code": code,
                }
            )

        spouse = _spouse_household_action(case_id_str, case, people)
        if spouse:
            actions.append(spouse)

        actions.sort(key=lambda a: (a.get("priority", 99), a.get("action_title") or ""))
        base["actions"] = actions
        base["meta"]["action_count"] = len(actions)
        return base


def list_next_actions(conn: Connection, case_id_raw: Optional[str]) -> Dict[str, Any]:
    return NextActionService().list_actions(conn, case_id_raw)
