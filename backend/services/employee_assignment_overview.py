"""
Compact employee assignment overview for dashboard bootstrap (no case hydration).
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from ..database import Database

log = logging.getLogger(__name__)


def _json_scalar(v: Any) -> Any:
    """Ensure JSON-serializable scalars (Postgres may return UUID/datetime/Decimal in row mappings)."""
    if v is None:
        return None
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _destination_payload(host: Optional[str], home: Optional[str]) -> Dict[str, Any]:
    h = (host or "").strip()
    o = (home or "").strip()
    if h and o:
        label = f"{o} → {h}"
    else:
        label = h or o or None
    return {
        "label": label,
        "host_country": h or None,
        "home_country": o or None,
    }


def _claim_summary(statuses: List[str]) -> Dict[str, Any]:
    """Derive claim UX hints from assignment_claim_invites statuses (lowercase)."""
    if not statuses:
        state = "no_invite"
    elif "pending" in statuses:
        state = "invite_pending"
    elif "claimed" in statuses:
        state = "invite_claimed"
    elif all(x == "revoked" for x in statuses):
        state = "invite_revoked"
    else:
        state = "mixed"
    extra = state in ("invite_revoked", "mixed")
    return {
        "state": state,
        "requires_explicit_claim": True,
        "extra_verification_required": extra,
    }


def build_employee_assignment_overview(
    db: Database,
    employee_user_id: str,
    *,
    request_id: Optional[str] = None,
    normalize_assignment_status: Callable[[Optional[str]], str],
) -> Dict[str, Any]:
    uid = (employee_user_id or "").strip()
    linked_rows: List[Dict[str, Any]] = []
    pending_rows: List[Dict[str, Any]] = []
    try:
        linked_rows = db.list_employee_linked_assignment_overview(uid, request_id=request_id)
    except Exception as e:
        log.warning(
            "list_employee_linked_assignment_overview failed user=%s request_id=%s: %s",
            uid,
            request_id,
            e,
            exc_info=True,
        )
    try:
        pending_rows = db.list_employee_pending_assignment_overview(uid, request_id=request_id)
    except Exception as e:
        log.warning(
            "list_employee_pending_assignment_overview failed user=%s request_id=%s: %s",
            uid,
            request_id,
            e,
            exc_info=True,
        )
    pending_ids = [str(x) for x in (r.get("assignment_id") for r in pending_rows) if x]
    invite_map: Dict[str, List[str]] = {}
    try:
        invite_map = db.map_claim_invite_statuses_by_assignments(pending_ids, request_id=request_id)
    except Exception as e:
        log.warning(
            "map_claim_invite_statuses_by_assignments failed request_id=%s: %s",
            request_id,
            e,
            exc_info=True,
        )

    linked_out: List[Dict[str, Any]] = []
    for r in linked_rows:
        linked_out.append(
            {
                "assignment_id": _json_scalar(r.get("assignment_id")),
                "case_id": _json_scalar(r.get("case_id")),
                "company": {
                    "id": _json_scalar(r.get("company_id")),
                    "name": _json_scalar(r.get("company_name")),
                },
                "destination": _destination_payload(r.get("host_country"), r.get("home_country")),
                "status": normalize_assignment_status(r.get("assignment_status")),
                "created_at": _json_scalar(r.get("assignment_created_at")),
                "updated_at": _json_scalar(r.get("assignment_updated_at")),
                "current_stage": _json_scalar(r.get("relocation_stage")),
                "relocation_case_status": _json_scalar(r.get("relocation_case_status")),
            }
        )

    pending_out: List[Dict[str, Any]] = []
    for r in pending_rows:
        aid = r.get("assignment_id")
        aid_s = str(aid) if aid else ""
        st_list = invite_map.get(aid_s, []) if aid_s else []
        pending_out.append(
            {
                "assignment_id": _json_scalar(aid),
                "case_id": _json_scalar(r.get("case_id")),
                "company": {
                    "id": _json_scalar(r.get("company_id")),
                    "name": _json_scalar(r.get("company_name")),
                },
                "destination": _destination_payload(r.get("host_country"), r.get("home_country")),
                "created_at": _json_scalar(r.get("assignment_created_at")),
                "claim": _claim_summary(st_list),
            }
        )

    return {"linked": linked_out, "pending": pending_out}
