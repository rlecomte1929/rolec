"""
Company-scoped authorization for policy assistant import, snapshots, diffs, and audits.

Backend-only; do not rely on frontend for access control.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException

from ..database import Database


def user_can_access_company(user: Dict[str, Any], company_id: Optional[str], db: Database) -> bool:
    if not company_id:
        return False
    if user.get("is_admin"):
        return True
    prof = db.get_profile_record(user.get("id")) or {}
    return str(prof.get("company_id") or "") == str(company_id).strip()


def require_company_access(user: Dict[str, Any], company_id: str, db: Database) -> None:
    if user_can_access_company(user, company_id, db):
        return
    raise HTTPException(status_code=404, detail="Not found")


def require_snapshot_company_access(
    user: Dict[str, Any],
    db: Database,
    snapshot_row: Optional[Dict[str, Any]],
) -> None:
    if not snapshot_row:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    cid = str(snapshot_row.get("company_id") or "")
    require_company_access(user, cid, db)


def require_document_company_access(
    user: Dict[str, Any],
    db: Database,
    doc: Optional[Dict[str, Any]],
) -> None:
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    cid = str(doc.get("company_id") or "")
    require_company_access(user, cid, db)


def require_two_snapshots_same_company(
    db: Database,
    older_id: str,
    newer_id: str,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    a = db.get_policy_knowledge_snapshot_by_id(older_id)
    b = db.get_policy_knowledge_snapshot_by_id(newer_id)
    if not a or not b:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    if str(a.get("company_id")) != str(b.get("company_id")):
        raise HTTPException(status_code=400, detail="Snapshots must belong to the same company")
    return a, b
