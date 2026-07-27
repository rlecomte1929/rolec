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
from ...database import db, _jbind
from ..services.audit_log_service import (
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


def _canonical_services_case_id(case_id: str) -> str:
    """Resolve a route id to the canonical case_id `services_state` is keyed on.

    [AIQ-1704 / AIQ-1717] `require_case_access` authorizes ANY of the three id forms
    (assignment PK, case_id, canonical_case_id — see `get_assignment_by_case_id`), but
    every query below binds the RAW path param. So a request that authorized with an
    ASSIGNMENT id used to read nothing and, worse, INSERT a phantom `services_state`
    row keyed on that assignment id — a row the read path can never find again.
    `services_state.case_id` is UNIQUE, so a case can only ever hold one of the two
    keys. One such phantom row exists in production.

    Resolve when we can; otherwise return the id unchanged. The fallback is NOT the
    fail-open this epic exists to kill: `resolve_case_ids` goes through
    `case_assignments`, so it returns None for a case that has no assignment row —
    the HR-wizard flow `require_case_access` explicitly supports (it returns `{}`
    there rather than 404ing). Ten such rows are live in production, keyed on a
    `wizard_cases` id. For those the raw id IS the canonical key, so passing it
    through is correct; the dangerous case — the raw id being an assignment id — is
    exactly what the resolve above catches.
    """
    ids = db.resolve_case_ids(case_id)
    return ids.canonical_case_id if ids else case_id


def _org_id_for_case(case_id: str, assignment: Dict[str, Any]) -> str:
    """Derive the case's tenant from the case record itself — the canonical
    source of truth — rather than from the caller's profile.

    [AIQ-1012] Production-shaped employees often have no profiles.company_id
    (their company association is through the assignment, not a profile field),
    so deriving the tenant from the caller 403'd valid case owners. Call this
    only AFTER require_case_access has authorized the caller for the case.
    Falls back to the assignment's HR user's company when the relocation_cases
    row carries no company_id.
    """
    case = db.get_case_by_id(case_id) or {}
    org = case.get("company_id")
    if not org and assignment:
        org = db.get_hr_company_id(assignment.get("hr_user_id"))
    if not org:
        raise HTTPException(
            status_code=403,
            detail="Case has no tenant — cannot resolve services state.",
        )
    return org


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


def _parse_state_json(raw: Any) -> Dict[str, Any]:
    """Normalise a stored services-state blob to a dict.

    state_json is a JSONB column: psycopg2 returns it ALREADY PARSED (a dict) on
    Postgres, while SQLite (tests) stores it as TEXT and returns a str. The old
    code called json.loads() unconditionally, so on Postgres json.loads(<dict>)
    raised TypeError → every GET 404'd "could not be parsed" once a row existed
    (AIQ-1320 — only surfaced after the save path was unblocked). Handle both.
    """
    if raw is None or raw == "":
        return {}
    if isinstance(raw, (dict, list)):
        return raw  # already parsed from JSONB (Postgres)
    return json.loads(raw)  # TEXT column on SQLite — may raise, caught by caller


@router.get(
    "/api/cases/{case_id}/services-state",
    response_model=ServicesStateRead,
)
def get_services_state(
    case_id: str,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    # Authorize the case FIRST (employees must own it; HR scoped to their
    # company), then derive the tenant from the case record — not the caller's
    # profile (AIQ-1012). require_case_access returns the assignment row.
    assignment = require_case_access(case_id, user)
    case_id = _canonical_services_case_id(case_id)
    organization_id = _org_id_for_case(case_id, assignment)
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT case_id, organization_id, state_json, updated_at, updated_by_user_id "
                "FROM services_state WHERE case_id = :id AND organization_id = :org"
            ),
            {"id": case_id, "org": organization_id},
        ).mappings().first()
    if not row:
        # No saved state yet is the normal fresh-visit case — return an empty
        # state with 200 (not 404). A 404 here is swallowed by the client but
        # the browser still logs a console error on every first services visit
        # (AIQ-1320). The authorize-first guard above still 403/404s real access
        # problems; this only changes the "authorized but nothing saved" path.
        return {
            "case_id": case_id,
            "organization_id": organization_id,
            "state": {},
            "updated_at": "",
            "updated_by_user_id": None,
        }
    try:
        parsed = _parse_state_json(row["state_json"])
    except (TypeError, ValueError):
        # Stored blob is genuinely corrupt — surface as 404 rather than 500 so the
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
    # Authorize the case FIRST (employees must own it; HR scoped to their
    # company), then derive the tenant from the case record — not the caller's
    # profile (AIQ-1012). require_case_access returns the assignment row.
    assignment = require_case_access(case_id, user)
    case_id = _canonical_services_case_id(case_id)
    organization_id = _org_id_for_case(case_id, assignment)
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
                    f"SET state_json = {_jbind('blob')}, updated_at = :now, updated_by_user_id = :actor "
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
                    f"VALUES (:id, :org, {_jbind('blob')}, :now, :actor)"
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

    # Bridge the current service selection into the roadmap. Best-effort +
    # idempotent — a reconcile failure must never fail the state save.
    try:
        from ..services.service_roadmap_bridge import reconcile_service_milestones
        selected = body.state.get("selectedServices") if isinstance(body.state, dict) else None
        if isinstance(selected, list):
            reconcile_service_milestones(db, case_id, selected)
    except Exception:  # noqa: BLE001 — non-fatal best-effort bridge
        logger.warning("services-state: roadmap reconcile failed for case %s", case_id, exc_info=True)

    return {
        "case_id": case_id,
        "organization_id": organization_id,
        "state": body.state,
        "updated_at": now,
        "updated_by_user_id": actor_id,
    }
