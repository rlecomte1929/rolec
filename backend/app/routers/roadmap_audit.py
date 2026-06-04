"""
P1-08 · Roadmap audit-trail endpoints (AIQ-202 parent).

  - GET  /api/cases/{case_id}/audit?as_of=<date>           (P1-08c / AIQ-641)
        Reconstruct the roadmap as it existed on a past date — the rule_version
        in effect at that date for every rule cited on the case. HR/Admin only,
        tenant-scoped (404 on cross-tenant, mirroring hr_case_audit).

  - GET  /api/admin/cases/{case_id}/audit-export.json      (P1-08e / AIQ-643)
        Schema-versioned JSON export of the full audit trail for legal
        proceedings. Admin only.

  - POST /api/admin/rule-change-notifications/run          (P1-08d / AIQ-642)
        Manually trigger the rule-change notifier (normally scheduled). Admin
        only. Returns the run counts.

DB/tenant patterns mirror backend/app/routers/hr_case_audit.py (C1-16): raw SQL
over the rce.* ontology via database.db, 404 on cross-tenant access, and a
graceful degrade to empty results when the rce.* tables are not yet present.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..auth_deps import get_org_id_for_hr_user, require_admin, require_admin_or_hr
from ..services.roadmap_audit_service import (
    export_case_audit,
    reconstruct_roadmap_as_of,
)
from ..services.rule_change_notifier import notify_superseded_rules
from ...database import db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["roadmap-audit"])


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


class ReconstructResponse(BaseModel):
    case_id: str
    as_of: Optional[str] = None
    steps: List[Dict[str, Any]] = Field(default_factory=list)


class NotifierRunResponse(BaseModel):
    affected_pairs: int = 0
    notifications_created: int = 0
    skipped_idempotent: int = 0
    skipped_no_recipient: int = 0


# ---------------------------------------------------------------------------
# Tenant gate — identical contract to hr_case_audit._require_case_access
# ---------------------------------------------------------------------------


def _require_case_access(case_id: str, org_id: str) -> Dict[str, Any]:
    """404 (not 403) on missing or cross-tenant case, so ids can't be probed."""
    row = db.get_relocation_case(case_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    case_company_id = row.get("company_id")
    if case_company_id and case_company_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return row


# ---------------------------------------------------------------------------
# P1-08c — as_of reconstruction
# ---------------------------------------------------------------------------


@router.get("/api/cases/{case_id}/audit", response_model=ReconstructResponse)
def get_roadmap_audit_as_of(
    case_id: str,
    as_of: Optional[date] = Query(
        None, description="Reconstruct the roadmap as it existed on this date (YYYY-MM-DD). Omit for current state."
    ),
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> ReconstructResponse:
    """Roadmap reconstruction: rule_version in effect on ``as_of`` per cited step."""
    _require_case_access(case_id, org_id)
    try:
        steps = reconstruct_roadmap_as_of(case_id, as_of)
    except Exception:  # noqa: BLE001 — rce.* not present yet → empty, not 500
        logger.exception("roadmap_audit: reconstruction failed case=%s", case_id)
        steps = []
    return ReconstructResponse(
        case_id=case_id,
        as_of=as_of.isoformat() if as_of else None,
        steps=steps,
    )


# ---------------------------------------------------------------------------
# P1-08e — legal JSON export (admin only)
# ---------------------------------------------------------------------------


@router.get("/api/admin/cases/{case_id}/audit-export.json")
def get_audit_export(
    case_id: str,
    _admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Full, schema-versioned audit-trail export for one case (legal proceedings)."""
    try:
        return export_case_audit(case_id)
    except Exception:  # noqa: BLE001 — rce.* not present yet → empty export, not 500
        logger.exception("roadmap_audit: export failed case=%s", case_id)
        from ..services.roadmap_audit_service import AUDIT_EXPORT_SCHEMA_VERSION

        return {
            "schema_version": AUDIT_EXPORT_SCHEMA_VERSION,
            "case_id": case_id,
            "exported_at": None,
            "entry_count": 0,
            "audit_log": [],
        }


# ---------------------------------------------------------------------------
# P1-08d — manual notifier trigger (admin only; normally scheduled)
# ---------------------------------------------------------------------------


@router.post("/api/admin/rule-change-notifications/run", response_model=NotifierRunResponse)
def run_rule_change_notifications(
    _admin: Dict[str, Any] = Depends(require_admin),
) -> NotifierRunResponse:
    """Trigger the rule-change notifier now. Returns the run counts."""
    try:
        counts = notify_superseded_rules()
    except Exception:  # noqa: BLE001 — degrade rather than 500
        logger.exception("roadmap_audit: rule-change notifier run failed")
        counts = {}
    return NotifierRunResponse(**counts)
