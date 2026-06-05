"""
HR Case Detail — case-scoped reads consumed by the C1-11c frontend.

Six endpoints powering the HR dashboard's per-case surface:

  GET /api/hr/cases/{case_id}/overview
  GET /api/hr/cases/{case_id}/documents
  GET /api/hr/cases/{case_id}/steps
  GET /api/hr/cases/{case_id}/contradictions/summary
  GET /api/hr/cases/{case_id}/contradictions
  GET /api/hr/cases/{case_id}/contradictions/{contradiction_id}/history

Tenant scoping (RLS): every route returns 404 on a tenant mismatch,
not 403, so an attacker can't enumerate case ids by status code. The
auth pattern mirrors `/api/hr/cases` in backend/main.py — JWT →
require_admin_or_hr → org_id check vs relocation_cases.company_id.

Schema bridge: the HR dashboard's URL :id param is `relocation_cases.id`
(the legacy primary table). The new Case Engine schema (rce.*) keys
off the same UUID for documents, contradictions, and family members,
so a join through `case_id` works in both directions. Where the bridge
is incomplete (e.g. rce.cases ↔ relocation_cases linkage isn't fully
wired yet), we read the legacy row for overview meta and the rce row
for engine-derived data.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ...database import db


router = APIRouter(prefix="/api/hr/cases", tags=["hr-case-detail"])


# ---------------------------------------------------------------------------
# Pydantic response shapes (mirror apps/hr-dashboard/src/features/case-detail/types.ts)
# ---------------------------------------------------------------------------


class FamilyMemberDTO(BaseModel):
    family_member_id: str
    relationship: str
    display_name: str
    date_of_birth: Optional[str] = None
    is_dependent: Optional[bool] = None


class EmployeeDTO(BaseModel):
    employee_id: str
    display_name: str
    primary_email: Optional[str] = None
    nationality: Optional[str] = None


class CaseOverviewDTO(BaseModel):
    case_id: str
    employee: EmployeeDTO
    origin_country_code: Optional[str] = None
    dest_country_code: Optional[str] = None
    corridor: Optional[str] = None
    status: str
    stage: Optional[str] = None
    target_start_date: Optional[str] = None
    actual_start_date: Optional[str] = None
    target_close_date: Optional[str] = None
    family_members: List[FamilyMemberDTO] = Field(default_factory=list)


class OverviewResponse(BaseModel):
    overview: CaseOverviewDTO


class CaseDocumentDTO(BaseModel):
    document_id: str
    document_type_code: str
    document_type_label: Optional[str] = None
    filename: str
    uploaded_at: str
    confidence_mean: Optional[float] = None
    confidence_min: Optional[float] = None
    extracted_field_count: Optional[int] = None
    document_uri: Optional[str] = None
    page_count: Optional[int] = None


class DocumentsResponse(BaseModel):
    documents: List[CaseDocumentDTO] = Field(default_factory=list)


class CaseCitationDTO(BaseModel):
    legal_reference: Optional[str] = None
    source_url: Optional[str] = None


class CaseStepDTO(BaseModel):
    step_id: str
    label: str
    status: str
    due_date: Optional[str] = None
    owner_label: Optional[str] = None
    # C2-07 StepGraph fields (sourced from rce.steps / rce.deadlines / rce.rule_citations).
    prerequisite_step_ids: List[str] = Field(default_factory=list)
    expected_duration_days: Optional[int] = None
    derivation: Optional[str] = None  # legal derivation of the deadline, if any
    citations: List[CaseCitationDTO] = Field(default_factory=list)


class StepsResponse(BaseModel):
    steps: List[CaseStepDTO] = Field(default_factory=list)


class ContradictionsSummaryDTO(BaseModel):
    case_id: str
    total: int
    pending: int
    resolved: int


class ContradictionsSummaryResponse(BaseModel):
    summary: ContradictionsSummaryDTO


class CandidateDTO(BaseModel):
    candidate_id: str
    value_raw: str
    value_canonical: Optional[Dict[str, Any]] = None
    document_id: str
    document_type_code: Optional[str] = None
    source_agent_run_id: Optional[str] = None
    confidence: float
    bbox_page: Optional[int] = None
    bbox: Optional[List[int]] = None
    source_label: Optional[str] = None


class ContradictionDTO(BaseModel):
    contradiction_id: str
    case_id: str
    canonical_entity_id: Optional[str] = None
    canonical_entity_label: Optional[str] = None
    field_key: str
    type: str
    candidates: List[CandidateDTO] = Field(default_factory=list)
    resolution_status: str
    suggested_winner: Optional[Any] = None
    content_hash: str
    detected_at: str
    detected_by: str


class ContradictionsListResponse(BaseModel):
    contradictions: List[ContradictionDTO] = Field(default_factory=list)


class PriorCorrectionDTO(BaseModel):
    correction_id: str
    field: str
    reason_code: str
    reason_freetext: Optional[str] = None
    corrected_at: str
    corrected_by_label: Optional[str] = None


class CorrectionHistoryResponse(BaseModel):
    corrections: List[PriorCorrectionDTO] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Auth helper — load the case, verify tenant, 404 if either fails.
# ---------------------------------------------------------------------------


def _require_case_access(case_id: str, org_id: str) -> Dict[str, Any]:
    """
    Return the relocation_cases row (as dict) if the caller's org owns it.

    404 (NOT 403) on tenant mismatch so an attacker can't probe which
    UUIDs belong to other tenants by reading status codes.
    """
    row = db.get_relocation_case(case_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    case_company_id = row.get("company_id")
    if case_company_id and case_company_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return row


# ---------------------------------------------------------------------------
# 1. GET /overview
# ---------------------------------------------------------------------------


_FAMILY_RELATIONSHIP_MAP = {
    "SPOUSE": "spouse",
    "CHILD": "child",
    "DEPENDENT_PARENT": "parent",
}


@router.get("/{case_id}/overview", response_model=OverviewResponse)
def get_case_overview(
    case_id: str,
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> OverviewResponse:
    case = _require_case_access(case_id, org_id)

    employee_id = case.get("employee_id") or ""
    employee_name: str = ""
    employee_email: Optional[str] = None
    if employee_id:
        try:
            user = db.get_user_by_id(employee_id)
        except Exception:
            user = None
        if user:
            employee_name = user.get("name") or user.get("email") or employee_id
            employee_email = user.get("email")

    family_members: List[FamilyMemberDTO] = []
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT family_member_id, relationship_type, canonical_entity_id
                    FROM rce.family_members
                    WHERE case_id = :case_id
                    ORDER BY created_at ASC
                    """
                ),
                {"case_id": case_id},
            ).mappings().all()
        for r in rows:
            relationship_raw = (r.get("relationship_type") or "").upper()
            family_members.append(
                FamilyMemberDTO(
                    family_member_id=str(r["family_member_id"]),
                    relationship=_FAMILY_RELATIONSHIP_MAP.get(relationship_raw, relationship_raw.lower() or "other"),
                    display_name=str(r.get("canonical_entity_id") or "Family member")[:8],
                    is_dependent=relationship_raw in ("CHILD", "DEPENDENT_PARENT"),
                )
            )
    except Exception:
        # rce.family_members may not be populated yet for legacy cases — non-fatal.
        family_members = []

    overview = CaseOverviewDTO(
        case_id=case_id,
        employee=EmployeeDTO(
            employee_id=employee_id,
            display_name=employee_name or f"Case {case_id[:8]}",
            primary_email=employee_email,
            nationality=case.get("nationality") or None,
        ),
        origin_country_code=case.get("origin_country_code"),
        dest_country_code=case.get("dest_country_code"),
        corridor=case.get("corridor"),
        status=str(case.get("status") or "draft"),
        stage=case.get("stage"),
        target_start_date=str(case["target_start_date"]) if case.get("target_start_date") else None,
        actual_start_date=str(case["actual_start_date"]) if case.get("actual_start_date") else None,
        target_close_date=str(case["target_close_date"]) if case.get("target_close_date") else None,
        family_members=family_members,
    )
    return OverviewResponse(overview=overview)


# ---------------------------------------------------------------------------
# 2. GET /documents
# ---------------------------------------------------------------------------


@router.get("/{case_id}/documents", response_model=DocumentsResponse)
def get_case_documents(
    case_id: str,
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> DocumentsResponse:
    _require_case_access(case_id, org_id)
    documents: List[CaseDocumentDTO] = []
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                      d.document_id,
                      d.original_filename,
                      d.storage_uri,
                      d.created_at,
                      dt.code AS document_type_code,
                      dt.label AS document_type_label,
                      ef_stats.mean_confidence,
                      ef_stats.min_confidence,
                      ef_stats.field_count
                    FROM rce.documents d
                    LEFT JOIN rce.document_types dt
                      ON dt.document_type_id = d.document_type_id
                    LEFT JOIN (
                      SELECT
                        document_id,
                        AVG(confidence)::float AS mean_confidence,
                        MIN(confidence)::float AS min_confidence,
                        COUNT(*)::int AS field_count
                      FROM rce.extracted_fields
                      GROUP BY document_id
                    ) ef_stats ON ef_stats.document_id = d.document_id
                    WHERE d.case_id = :case_id
                    ORDER BY d.created_at DESC
                    """
                ),
                {"case_id": case_id},
            ).mappings().all()

        for r in rows:
            documents.append(
                CaseDocumentDTO(
                    document_id=str(r["document_id"]),
                    document_type_code=str(r.get("document_type_code") or "UNKNOWN"),
                    document_type_label=r.get("document_type_label"),
                    filename=str(r.get("original_filename") or f"document-{str(r['document_id'])[:8]}"),
                    uploaded_at=r["created_at"].isoformat() if r.get("created_at") else "",
                    confidence_mean=r.get("mean_confidence"),
                    confidence_min=r.get("min_confidence"),
                    extracted_field_count=r.get("field_count"),
                    document_uri=r.get("storage_uri"),
                    page_count=None,
                )
            )
    except Exception:
        # rce.documents table may not exist in legacy environments — degrade
        # gracefully with an empty list so the frontend renders the empty
        # state instead of an error banner.
        documents = []

    return DocumentsResponse(documents=documents)


# ---------------------------------------------------------------------------
# 3. GET /steps
# ---------------------------------------------------------------------------


@router.get("/{case_id}/steps", response_model=StepsResponse)
def get_case_steps(
    case_id: str,
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> StepsResponse:
    import json

    _require_case_access(case_id, org_id)
    steps: List[CaseStepDTO] = []
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                      s.step_id,
                      s.name AS label,
                      s.responsible_party AS owner_label,
                      s.expected_duration_days,
                      COALESCE(s.prerequisite_step_ids, '{}')::text[] AS prerequisite_step_ids,
                      dl.due_date,
                      dl.derivation,
                      COALESCE(
                        (
                          SELECT json_agg(json_build_object(
                                   'legal_reference', rc.legal_reference,
                                   'source_url', rc.source_url))
                          FROM rce.rule_citations rc
                          WHERE rc.case_id = :case_id
                            AND rc.output_kind = 'STEP'
                            AND rc.output_id = s.step_id
                        ),
                        '[]'::json
                      ) AS citations
                    FROM rce.steps s
                    LEFT JOIN rce.deadlines dl
                      ON dl.step_id = s.step_id AND dl.case_id = :case_id
                    WHERE s.corridor_id IS NULL
                       OR s.corridor_id = (
                         SELECT corridor_id FROM rce.cases WHERE case_id = :case_id LIMIT 1
                       )
                    ORDER BY s.created_at ASC
                    """
                ),
                {"case_id": case_id},
            ).mappings().all()
        for r in rows:
            raw_citations = r.get("citations")
            if isinstance(raw_citations, str):
                raw_citations = json.loads(raw_citations)
            citations = [
                CaseCitationDTO(
                    legal_reference=c.get("legal_reference"),
                    source_url=c.get("source_url"),
                )
                for c in (raw_citations or [])
                if c
            ]
            steps.append(
                CaseStepDTO(
                    step_id=str(r["step_id"]),
                    label=str(r.get("label") or "Step"),
                    # Per-case step status is not yet tracked in rce.* (no completion
                    # signal exists pre-launch); default to "pending" until a step
                    # state machine lands. The frontend renders this faithfully.
                    status="pending",
                    due_date=r["due_date"].isoformat() if r.get("due_date") else None,
                    owner_label=r.get("owner_label"),
                    prerequisite_step_ids=[str(p) for p in (r.get("prerequisite_step_ids") or [])],
                    expected_duration_days=r.get("expected_duration_days"),
                    derivation=r.get("derivation"),
                    citations=citations,
                )
            )
    except Exception:
        steps = []
    return StepsResponse(steps=steps)


# ---------------------------------------------------------------------------
# 4. GET /contradictions/summary
# ---------------------------------------------------------------------------


@router.get("/{case_id}/contradictions/summary", response_model=ContradictionsSummaryResponse)
def get_contradictions_summary(
    case_id: str,
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> ContradictionsSummaryResponse:
    _require_case_access(case_id, org_id)
    total = pending = resolved = 0
    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT
                      COUNT(*)::int AS total,
                      COUNT(*) FILTER (
                        WHERE resolution_status IN ('Requires attention','Not resolved','No result')
                      )::int AS pending,
                      COUNT(*) FILTER (WHERE resolution_status = 'Resolved')::int AS resolved
                    FROM rce.contradictions
                    WHERE case_id = :case_id
                    """
                ),
                {"case_id": case_id},
            ).mappings().one_or_none()
        if row:
            total = int(row.get("total") or 0)
            pending = int(row.get("pending") or 0)
            resolved = int(row.get("resolved") or 0)
    except Exception:
        # rce.contradictions table lands with C1-08 — until then return zeroes
        # so the frontend renders the "all clear" empty state.
        pass

    return ContradictionsSummaryResponse(
        summary=ContradictionsSummaryDTO(
            case_id=case_id, total=total, pending=pending, resolved=resolved
        )
    )


# ---------------------------------------------------------------------------
# 5. GET /contradictions (list)
# ---------------------------------------------------------------------------


@router.get("/{case_id}/contradictions", response_model=ContradictionsListResponse)
def list_case_contradictions(
    case_id: str,
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> ContradictionsListResponse:
    _require_case_access(case_id, org_id)
    contradictions: List[ContradictionDTO] = []
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                      contradiction_id,
                      case_id,
                      canonical_entity_id,
                      field_key,
                      contradiction_type,
                      candidates,
                      resolution_status,
                      suggested_winner,
                      content_hash,
                      detected_at,
                      detected_by
                    FROM rce.contradictions
                    WHERE case_id = :case_id
                    ORDER BY detected_at DESC
                    """
                ),
                {"case_id": case_id},
            ).mappings().all()

        for r in rows:
            raw_candidates = r.get("candidates") or []
            candidates: List[CandidateDTO] = []
            for c in raw_candidates if isinstance(raw_candidates, list) else []:
                candidates.append(
                    CandidateDTO(
                        candidate_id=str(c.get("candidate_id") or c.get("document_id") or ""),
                        value_raw=str(c.get("value_raw") or c.get("value") or ""),
                        value_canonical=c.get("value_canonical"),
                        document_id=str(c.get("document_id") or ""),
                        document_type_code=c.get("document_type_code"),
                        source_agent_run_id=c.get("source_agent_run_id"),
                        confidence=float(c.get("confidence") or 0.0),
                        bbox_page=c.get("bbox_page"),
                        bbox=c.get("bbox"),
                        source_label=c.get("source_label"),
                    )
                )

            contradictions.append(
                ContradictionDTO(
                    contradiction_id=str(r["contradiction_id"]),
                    case_id=str(r["case_id"]),
                    canonical_entity_id=str(r["canonical_entity_id"]) if r.get("canonical_entity_id") else None,
                    field_key=str(r["field_key"]),
                    type=str(r["contradiction_type"]),
                    candidates=candidates,
                    resolution_status=str(r["resolution_status"]),
                    suggested_winner=r.get("suggested_winner"),
                    content_hash=str(r["content_hash"]),
                    detected_at=r["detected_at"].isoformat() if r.get("detected_at") else "",
                    detected_by=str(r.get("detected_by") or "agent_contradiction_v1"),
                )
            )
    except Exception:
        contradictions = []

    return ContradictionsListResponse(contradictions=contradictions)


# ---------------------------------------------------------------------------
# 6. GET /contradictions/{cid}/history
# ---------------------------------------------------------------------------


_LAST_N_CORRECTIONS = 5


@router.get(
    "/{case_id}/contradictions/{contradiction_id}/history",
    response_model=CorrectionHistoryResponse,
)
def get_contradiction_history(
    case_id: str,
    contradiction_id: str,
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> CorrectionHistoryResponse:
    """
    Last 5 prior corrections on the same (canonical_entity_id, field_key)
    as the target contradiction. Powers the C1-12 CorrectionHistory panel
    so reviewers can see whether a pattern is forming on this person /
    field before they pick a winner.
    """
    _require_case_access(case_id, org_id)
    corrections: List[PriorCorrectionDTO] = []
    try:
        with db.engine.connect() as conn:
            # Look up the canonical_entity + field_key for the target contradiction.
            target = conn.execute(
                text(
                    """
                    SELECT canonical_entity_id, field_key
                    FROM rce.contradictions
                    WHERE contradiction_id = :cid AND case_id = :case_id
                    """
                ),
                {"cid": contradiction_id, "case_id": case_id},
            ).mappings().one_or_none()
            if not target:
                return CorrectionHistoryResponse(corrections=[])
            entity_id = target.get("canonical_entity_id")
            field_key = target.get("field_key")
            if not entity_id or not field_key:
                return CorrectionHistoryResponse(corrections=[])

            rows = conn.execute(
                text(
                    """
                    SELECT
                      correction_id, field, reason_code, reason_freetext,
                      corrected_at, corrected_by
                    FROM rce.corrections
                    WHERE target_id = :entity_id AND field = :field_key
                    ORDER BY corrected_at DESC
                    LIMIT :n
                    """
                ),
                {"entity_id": entity_id, "field_key": field_key, "n": _LAST_N_CORRECTIONS},
            ).mappings().all()
        for r in rows:
            corrected_by_label: Optional[str] = None
            if r.get("corrected_by"):
                try:
                    user = db.get_user_by_id(str(r["corrected_by"]))
                    if user:
                        corrected_by_label = user.get("name") or user.get("email")
                except Exception:
                    corrected_by_label = None
            corrections.append(
                PriorCorrectionDTO(
                    correction_id=str(r["correction_id"]),
                    field=str(r["field"]),
                    reason_code=str(r["reason_code"]),
                    reason_freetext=r.get("reason_freetext"),
                    corrected_at=r["corrected_at"].isoformat() if r.get("corrected_at") else "",
                    corrected_by_label=corrected_by_label,
                )
            )
    except Exception:
        corrections = []

    return CorrectionHistoryResponse(corrections=corrections)
