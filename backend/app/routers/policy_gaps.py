"""Policy-gap reads for the HR case-detail surface (C2-06-FOLLOWUP).

  GET /api/hr/cases/{case_id}/policy-gaps

Returns the case's currently-unresolved policy-versus-reality gaps detected by
backend.relopass.policy_evidence (persisted into rce.policy_gaps by the
detect_and_persist adapter, which runs on case-lifecycle events). Read-only.

Auth mirrors backend/app/routers/hr_case_detail.py: JWT → require_admin_or_hr →
org_id checked against relocation_cases.company_id. Tenant mismatch returns 404
(not 403) so case ids can't be enumerated by status code. The URL :case_id is
relocation_cases.id, which the rce.* engine keys off the same UUID.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ...database import db


router = APIRouter(prefix="/api/hr/cases", tags=["policy-gaps"])


class ClauseRef(BaseModel):
    id: str
    type: str
    source_page: Optional[int] = None
    bbox: Optional[List[float]] = None


class SubjectRef(BaseModel):
    kind: str
    family_member_id: Optional[str] = None
    display_name: Optional[str] = None


class PolicyGapDTO(BaseModel):
    gap_id: str
    gap_type: str
    clause: ClauseRef
    subject: SubjectRef
    detected_at: str
    suggested_action: Optional[str] = None


class PolicyGapsResponse(BaseModel):
    gaps: List[PolicyGapDTO] = Field(default_factory=list)


def _require_case_access(case_id: str, org_id: str) -> Dict[str, Any]:
    """Return the relocation_cases row if the caller's org owns it, else 404."""
    row = db.get_relocation_case(case_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    case_company_id = row.get("company_id")
    if case_company_id and case_company_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return row


def _citation_page(citation: Optional[Dict[str, Any]]) -> Optional[int]:
    if not isinstance(citation, dict):
        return None
    page = citation.get("source_page", citation.get("page"))
    return int(page) if page is not None else None


def _citation_bbox(citation: Optional[Dict[str, Any]]) -> Optional[List[float]]:
    if not isinstance(citation, dict):
        return None
    bbox = citation.get("bbox")
    if isinstance(bbox, (list, tuple)):
        return [float(x) for x in bbox]
    return None


@router.get("/{case_id}/policy-gaps", response_model=PolicyGapsResponse)
def list_policy_gaps(
    case_id: str,
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> PolicyGapsResponse:
    _require_case_access(case_id, org_id)
    gaps: List[PolicyGapDTO] = []
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                      pg.gap_id,
                      pg.gap_type,
                      pg.policy_clause_id,
                      pg.clause_type,
                      pg.citation,
                      pg.subject_kind,
                      pg.family_member_id,
                      pg.suggested_action,
                      pg.detected_at,
                      ce.canonical_form AS subject_canonical_form
                    FROM rce.policy_gaps pg
                    LEFT JOIN rce.family_members fm
                      ON fm.family_member_id = pg.family_member_id
                    LEFT JOIN rce.canonical_entities ce
                      ON ce.canonical_entity_id = fm.canonical_entity_id
                    WHERE pg.case_id = :cid AND pg.cleared_at IS NULL
                    ORDER BY pg.detected_at DESC
                    """
                ),
                {"cid": case_id},
            ).mappings().all()

        for r in rows:
            citation = r.get("citation")
            form = r.get("subject_canonical_form")
            display_name: Optional[str] = None
            if isinstance(form, dict):
                display_name = form.get("display_name") or form.get("full_name")
            gaps.append(
                PolicyGapDTO(
                    gap_id=str(r["gap_id"]),
                    gap_type=str(r["gap_type"]),
                    clause=ClauseRef(
                        id=str(r["policy_clause_id"]),
                        type=str(r["clause_type"]),
                        source_page=_citation_page(citation),
                        bbox=_citation_bbox(citation),
                    ),
                    subject=SubjectRef(
                        kind=str(r["subject_kind"]),
                        family_member_id=str(r["family_member_id"])
                        if r.get("family_member_id")
                        else None,
                        display_name=display_name,
                    ),
                    detected_at=r["detected_at"].isoformat() if r.get("detected_at") else "",
                    suggested_action=r.get("suggested_action"),
                )
            )
    except HTTPException:
        raise
    except Exception:
        # rce.policy_gaps absent in legacy envs — degrade to empty list so the
        # HR dashboard renders the "no gaps" state instead of an error banner.
        gaps = []

    return PolicyGapsResponse(gaps=gaps)
