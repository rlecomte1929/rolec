"""[AIQ-1136 / NAV-HR-2-FU] Internal notes on a relocation case.

GET/POST /api/hr/cases/{case_id}/notes — lets HR annotate a case in context.
Company-scoped (the caller's resolved org must own the case; 404 on mismatch so
case ids can't be probed) and append-only. The POST is audited via the canonical
audit_logs (best-effort).

Registered in BOTH backend/app/main.py and backend/main.py — Render boots
backend.main:app, so a router registered only in app/main.py would 405 in prod.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ...database import db

router = APIRouter(prefix="/api/hr/cases", tags=["hr-case-notes"])


class CaseNote(BaseModel):
    id: str
    case_id: str
    author_user_id: str
    author_name: Optional[str] = None
    body: str
    created_at: str


class AddNoteBody(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


def _require_case_access(case_id: str, org_id: str) -> Dict[str, Any]:
    """Mirror hr_case_audit._require_case_access — 404 (not 403) on tenant mismatch."""
    row = db.get_relocation_case(case_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    case_company_id = row.get("company_id")
    if case_company_id and case_company_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return row


def _row(r: Any) -> Dict[str, Any]:
    return {
        "id": r["id"],
        "case_id": r["case_id"],
        "author_user_id": r["author_user_id"],
        "author_name": r["author_name"],
        "body": r["body"],
        "created_at": str(r["created_at"]),
    }


@router.get("/{case_id}/notes", response_model=List[CaseNote])
def list_case_notes(
    case_id: str,
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> List[Dict[str, Any]]:
    """Newest-first list of internal notes for a case, scoped to the caller's company."""
    _require_case_access(case_id, org_id)
    with db.engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id::text AS id, case_id, author_user_id, author_name, body, created_at
                FROM case_notes
                WHERE case_id = :cid AND (company_id = :org OR company_id IS NULL)
                ORDER BY created_at DESC, id DESC
                LIMIT 200
                """
            ),
            {"cid": case_id, "org": org_id},
        ).mappings().all()
    return [_row(r) for r in rows]


@router.post("/{case_id}/notes", response_model=CaseNote, status_code=status.HTTP_201_CREATED)
def add_case_note(
    case_id: str,
    body: AddNoteBody,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """Append an internal note to a case. Company-scoped + audited (best-effort)."""
    _require_case_access(case_id, org_id)
    actor = hr_user.get("auth_uuid") or hr_user.get("id")
    author_name = hr_user.get("full_name") or hr_user.get("email")

    with db.engine.begin() as conn:
        created = conn.execute(
            text(
                """
                INSERT INTO case_notes (case_id, company_id, author_user_id, author_name, body)
                VALUES (:cid, :org, :uid, :name, :body)
                RETURNING id::text AS id, case_id, author_user_id, author_name, body, created_at
                """
            ),
            {"cid": case_id, "org": org_id, "uid": str(actor), "name": author_name, "body": body.body},
        ).mappings().first()

        # Best-effort audit into the canonical audit_logs (never blocks the note).
        try:
            from ..services.audit_log_service import insert_audit_log, ACTION_INSERT, ACTOR_HUMAN

            _uuid_re = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            import re

            actor_id = str(actor) if actor and re.match(_uuid_re, str(actor), re.I) else None
            insert_audit_log(
                conn,
                entity_type="case",
                entity_id=case_id,
                action_type=ACTION_INSERT,
                new_value={"event": "CASE_NOTE_ADDED"},
                actor_type=ACTOR_HUMAN,
                actor_id=actor_id,
            )
        except Exception:
            pass

    return _row(created)
