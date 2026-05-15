"""
Per-case persisted Services-flow wizard state.

Lets the employee step away from the Services flow (Select services →
Preferences → Recommendations → Estimate Review) and come back to the same
shortlist, answers, and currency without rebuilding from scratch. Until this
PR the state lived only in localStorage, which meant: cleared cache, browser
change, or accidental "Start over" → gone, with no recovery path.

Endpoints (all authenticated):
  GET /api/cases/{case_id}/services-state    — employee or HR in same tenant
  PUT /api/cases/{case_id}/services-state    — same; upserts the blob

Storage shape: a single JSON blob per case. Keeping the schema as-blob means
shape changes on the wizard don't need migrations. Tenant isolation: every
query filters on the caller's company_id; PUT enforces the case_id belongs to
the caller's tenant on overwrite. Audit: every PUT writes one audit_logs row.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import require_hr_or_employee, require_case_access
from ...database import db, _jb
from ...services.audit_log_service import (
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
    insert_audit_log,
)

router = APIRouter(tags=["services_state"])
logger = logging.getLogger(__name__)

# Cap state-blob size so a buggy client can't bloat the row. Generous for the
# wizard's actual payload (selectedServices + answers + recommendations +
# shortlist + displayCurrency) which is typically a few KB.
MAX_STATE_BYTES = 256_000


class ServicesStatePut(BaseModel):
    state: Dict[str, Any] = Field(..., description="Opaque wizard state blob.")


class ServicesStateRead(BaseModel):
    case_id: str
    organization_id: str
    state: Dict[str, Any]
    updated_at: str
    updated_by_user_id: Optional[str]


def _caller_company_id(user: Dict[str, Any]) -> str:
    profile = db.get_profile_record(user.get("id"))
    company_id = (profile or {}).get("company_id") or user.get("company")
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail="No company linked to this profile — services state needs a tenant.",
        )
    return company_id


def _audit(*, case_id: str, action: str, actor_id: str, byte_size: int) -> None:
    """Audit-log the save without storing the entire blob in audit_logs."""
    try:
        with db.engine.begin() as conn:
            insert_audit_log(
                conn,
                entity_type="services_state",
                entity_id=case_id,
                action_type=action,
                old_value=None,
                # Don't echo the whole blob into audit_logs; metadata is enough
                # to know who saved what when, and the row itself is the source
                # of truth for shape.
                new_value={"byte_size": byte_size},
                actor_type=ACTOR_HUMAN,
                actor_id=actor_id,
            )
    except Exception:
        logger.exception("audit_log write failed services_state case_id=%s", case_id)


@router.get(
    "/api/cases/{case_id}/services-state",
    response_model=ServicesStateRead,
)
def get_services_state(
    case_id: str,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    organization_id = _caller_company_id(user)
    # B21 fix: employees must own this case; HR is scoped to their company.
    require_case_access(case_id, user)
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT case_id, organization_id, state_json, updated_at, updated_by_user_id "
                "FROM services_state WHERE case_id = :id AND organization_id = :org"
            ),
            {"id": case_id, "org": organization_id},
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="No saved state for this case.")
    try:
        parsed = json.loads(row["state_json"]) if row["state_json"] else {}
    except (TypeError, ValueError):
        # Stored blob is corrupt — surface as 404 rather than 500 so the
        # client can fall back to its own local state.
        raise HTTPException(status_code=404, detail="Stored state could not be parsed.")
    updated_at = row["updated_at"]
    if hasattr(updated_at, "isoformat"):
        updated_at = updated_at.isoformat()
    return {
        "case_id": row["case_id"],
        "organization_id": row["organization_id"],
        "state": parsed,
        "updated_at": updated_at,
        "updated_by_user_id": row["updated_by_user_id"],
    }


@router.post(
    "/api/cases/{case_id}/services-state",
    response_model=ServicesStateRead,
)
def put_services_state(
    case_id: str,
    body: ServicesStatePut,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    organization_id = _caller_company_id(user)
    # B21 fix: employees must own this case; HR is scoped to their company.
    require_case_access(case_id, user)
    actor_id = user["id"]
    blob = json.dumps(body.state, default=str)
    if len(blob.encode("utf-8")) > MAX_STATE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"State payload exceeds {MAX_STATE_BYTES} bytes.",
        )
    now = datetime.utcnow().isoformat()

    with db.engine.begin() as conn:
        existing = conn.execute(
            text(
                "SELECT case_id, organization_id FROM services_state WHERE case_id = :id"
            ),
            {"id": case_id},
        ).mappings().first()
        if existing and existing["organization_id"] != organization_id:
            # Another tenant owns this case_id row — refuse without leaking
            # the existence (404, not 403).
            raise HTTPException(status_code=404, detail="Case not found in your tenant.")

        if existing:
            conn.execute(
                text(
                    f"UPDATE services_state "
                    f"SET state_json = :blob{_jb}, updated_at = :now, updated_by_user_id = :actor "
                    f"WHERE case_id = :id"
                ),
                {"blob": blob, "now": now, "actor": actor_id, "id": case_id},
            )
            action = ACTION_UPDATE
        else:
            conn.execute(
                text(
                    f"INSERT INTO services_state "
                    f"(case_id, organization_id, state_json, updated_at, updated_by_user_id) "
                    f"VALUES (:id, :org, :blob{_jb}, :now, :actor)"
                ),
                {
                    "id": case_id,
                    "org": organization_id,
                    "blob": blob,
                    "now": now,
                    "actor": actor_id,
                },
            )
            action = ACTION_INSERT

    _audit(case_id=case_id, action=action, actor_id=actor_id, byte_size=len(blob))
    return {
        "case_id": case_id,
        "organization_id": organization_id,
        "state": body.state,
        "updated_at": now,
        "updated_by_user_id": actor_id,
    }
