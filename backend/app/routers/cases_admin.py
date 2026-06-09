"""
cases_admin.py — DELETE endpoints + HR privileged ops extracted from cases.py
(AUDIT-B9-cases-5, re-scoped 2026-05-27).

Currently houses only delete_dossier — the admin bucket was empty per cases-1
recon (no require_admin-gated routes, no force-close, no bulk_* handlers exist
in cases.py). The stage was re-scoped to capture destructive ops so future
DELETE/admin handlers have a canonical home.

DORMANT: this router is not yet wired into backend/app/main.py. Canonical
registration still happens via cases.py until cases-6.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import text as _sql_text

from ..auth_deps import get_current_user
from ..services.audit_log_service import (
    ACTION_DELETE,
    ACTOR_HUMAN,
    insert_audit_log,
)
from ..services.case_service import (
    _assert_case_access,
    _pg_table,
)
from ...database import db as main_db

router = APIRouter(prefix="/api/cases", tags=["cases-admin"])
logger = logging.getLogger(__name__)


# ── [P3-6] Delete dossier ─────────────────────────────────────────────────────

@router.delete("/{case_id}/dossiers/{dossier_id}", status_code=204)
def delete_dossier(
    case_id: str,
    dossier_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    """[P3-6] Delete a DossierPackage record (does not remove the stored PDF)."""
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.begin() as conn:
            result = conn.execute(
                _sql_text(
                    f"""
                    DELETE FROM {_pg_table('dossier_packages')}
                    WHERE id = :did AND case_id = :cid
                    """
                ),
                {"did": dossier_id, "cid": case_id},
            )
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Dossier package not found")
            try:
                insert_audit_log(
                    conn,
                    entity_type="dossier_package",
                    entity_id=dossier_id,
                    action_type=ACTION_DELETE,
                    actor_type=ACTOR_HUMAN,
                    actor_id=user.get("id") or user.get("sub"),
                    new_value={"event": "dossier_deleted", "case_id": case_id},
                )
            except Exception:
                logger.exception("audit: delete_dossier dossier_id=%s", dossier_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("dossier: delete failed dossier_id=%s", dossier_id)
        raise HTTPException(status_code=500, detail="Failed to delete dossier")
    return Response(status_code=204)
