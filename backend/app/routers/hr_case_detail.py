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

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ..services.case_feasibility import feasibility_for_case
from ..services.contradiction_store_pg import run_contradiction_detection_for_case
from ...database import db


logger = logging.getLogger(__name__)

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


class CaseFeasibilityDTO(BaseModel):
    """Does the target start date leave room for the corridor to run? (AIQ-1749)

    Null on the overview when there is no opinion to give — an unresolvable
    corridor, no declared arrival anchor, or no target start date. Absent must
    render as nothing, never as reassurance.
    """

    verdict: str  # 'critical' | 'tight' | 'ok'
    required_days: int
    available_days: int
    derivation: str


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
    feasibility: Optional[CaseFeasibilityDTO] = None


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


class ExtractedFieldDTO(BaseModel):
    """One field the extraction engine read out of a document.

    `value` is already masked server-side for sensitive keys — see `_MASKED_FIELD_KEYS`.
    The client must not have to know which keys are sensitive to avoid leaking one.
    """
    field_key: str
    value: Optional[str] = None
    confidence: Optional[float] = None
    resolution_status: Optional[str] = None
    masked: bool = False
    page: Optional[int] = None


class ExtractedFieldsResponse(BaseModel):
    document_id: str
    document_type_code: Optional[str] = None
    # Deduplicated count. Deliberately NOT the raw row count: re-processing a document
    # APPENDS extracted_fields rather than replacing them, so the raw count over-reports
    # (the AIQ-1780 probe document reads 22 rows for 13 real fields).
    field_count: int = 0
    fields: List[ExtractedFieldDTO] = Field(default_factory=list)


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

    # Permit corridors need ~15 weeks of runway before the employee can even travel,
    # so a start date inside that window is unrecoverable however diligent the case
    # is. Resolution is fallback-safe: None when there is no opinion to give.
    assessment = feasibility_for_case(
        case.get("origin_country_code"),
        case.get("dest_country_code"),
        case.get("target_start_date"),
    )
    feasibility = (
        CaseFeasibilityDTO(
            verdict=assessment.verdict,
            required_days=assessment.required_days,
            available_days=assessment.available_days,
            derivation=assessment.derivation,
        )
        if assessment is not None
        else None
    )

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
        feasibility=feasibility,
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
                    # rce.document_types has no label column (only code,
                    # expected_fields_json, validator_pack). Clients fall back to the code.
                    document_type_label=None,
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
        # rce.documents may be absent in legacy environments — degrade to an empty list
        # so the frontend renders the empty state rather than an error banner.
        #
        # LOGGED, not swallowed. This block hid a hard `column dt.label does not exist`
        # for the entire life of the endpoint: every call raised, every call returned
        # [], and an empty list is indistinguishable from "this case has no documents".
        # The extraction pipeline had been producing fields in production for a day
        # before anyone noticed nothing could read them. A degrade path that reports
        # nothing is a place bugs go to live.
        logger.exception("hr_case_detail: documents query failed for case %s", case_id)
        documents = []

    return DocumentsResponse(documents=documents)


# ---------------------------------------------------------------------------
# 2b. GET /documents/{document_id}/fields
# ---------------------------------------------------------------------------
#
# [AIQ-1790] The values the extraction engine actually read. GET /documents above
# returns only AGGREGATES (field_count, mean/min confidence), so until this existed
# nothing could show a user *what* was extracted — the pipeline ran, produced 13
# structured passport fields in production, and the product displayed none of them.

# Masked in the response, not at the client. `document_number` is the passport number
# and `personal_number` the national ID / D-number; both identify a person on their own.
# Mirrors frontend PassportOCRFlow.tsx, which already renders the passport number as
# '••••••••' even in the employee's own review step.
#
# NOT driven by `rce.extracted_fields.phi_class`. When this endpoint was written, every
# one of the 22 production rows — passport document number included — carried
# phi_class='NONE', so trusting that column would have leaked.
#
# [AIQ-1805, 2026-08-11] The classifier is now fixed and those rows are backfilled, but
# this masking deliberately still keys on field_key. Classify first, prove it, and only
# then let something depend on it — retrofitting a protection onto a column that was
# wrong for months is how the wrong thing ships confidently. Switching this to phi_class
# is a separate, deliberate change.
_MASKED_FIELD_KEYS = frozenset({"document_number", "personal_number"})
_MASK = "••••••••"


@router.get("/{case_id}/documents/{document_id}/fields",
            response_model=ExtractedFieldsResponse)
def get_case_document_fields(
    case_id: str,
    document_id: str,
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> ExtractedFieldsResponse:
    _require_case_access(case_id, org_id)

    try:
        UUID(document_id)
    except (ValueError, AttributeError, TypeError):
        # Same 404-not-422 posture as the tenant check: a malformed id must not read
        # differently from one belonging to another tenant.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    fields: List[ExtractedFieldDTO] = []
    document_type_code: Optional[str] = None
    try:
        with db.engine.connect() as conn:
            doc = conn.execute(
                text(
                    """
                    SELECT d.document_id, dt.code AS document_type_code
                    FROM rce.documents d
                    LEFT JOIN rce.document_types dt
                      ON dt.document_type_id = d.document_type_id
                    WHERE d.document_id = CAST(:doc_id AS uuid)
                      AND d.case_id = :case_id
                    """
                ),
                {"doc_id": document_id, "case_id": case_id},
            ).mappings().first()
            if not doc:
                # Belongs to another case (or does not exist). 404 either way — the
                # caller already proved access to THIS case, not to that document.
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                    detail="Document not found")
            document_type_code = doc.get("document_type_code")

            rows = conn.execute(
                text(
                    """
                    SELECT ef.field_key,
                           ef.value_raw,
                           ef.confidence,
                           ef.resolution_status,
                           ef.bbox_page
                    FROM rce.extracted_fields ef
                    WHERE ef.document_id = CAST(:doc_id AS uuid)
                    ORDER BY ef.field_key, ef.created_at DESC
                    """
                ),
                {"doc_id": document_id},
            ).mappings().all()

        # Keep the newest row per field_key. Re-processing a document APPENDS to
        # extracted_fields rather than replacing, so a twice-processed document yields
        # every field twice — the production probe reads 22 rows for 13 real fields.
        #
        # Deliberately deduplicated here rather than with SQL `DISTINCT ON`: that is
        # Postgres-only syntax, and because these tests mock the engine it would make the
        # rule untestable — the assertion would only prove the fixture. The row counts are
        # tens, so the cost is nil. ORDER BY above makes "first seen wins" = "newest wins".
        seen: set = set()
        for r in rows:
            key = str(r["field_key"])
            if key in seen:
                continue
            seen.add(key)
            is_masked = key in _MASKED_FIELD_KEYS
            raw = r.get("value_raw")
            fields.append(
                ExtractedFieldDTO(
                    field_key=key,
                    value=(_MASK if (is_masked and raw) else raw),
                    confidence=float(r["confidence"]) if r.get("confidence") is not None else None,
                    resolution_status=r.get("resolution_status"),
                    masked=is_masked and bool(raw),
                    page=r.get("bbox_page"),
                )
            )
    except HTTPException:
        raise
    except Exception:
        # Matches GET /documents: rce.* may be absent in legacy environments. Degrade to
        # an empty list so the panel renders "not yet processed" rather than an error —
        # but log it, for the reason spelled out on that endpoint's handler.
        logger.exception(
            "hr_case_detail: extracted-fields query failed for case %s document %s",
            case_id, document_id,
        )
        fields = []

    return ExtractedFieldsResponse(
        document_id=document_id,
        document_type_code=document_type_code,
        field_count=len(fields),
        fields=fields,
    )


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


# ---------------------------------------------------------------------------
# 7. POST /contradictions/detect  (C2-09c — trigger the detector for a case)
# ---------------------------------------------------------------------------


class ContradictionDetectResponse(BaseModel):
    case_id: str
    # Number of contradictions freshly detected this run (idempotent — re-runs on
    # unchanged data return 0 because the store dedups on content_hash).
    detected: int
    contradiction_types: List[str] = Field(default_factory=list)


@router.post("/{case_id}/contradictions/detect", response_model=ContradictionDetectResponse)
def detect_case_contradictions(
    case_id: str,
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> ContradictionDetectResponse:
    """Run the C1-08/C2-09 contradiction detector across this case's extracted
    fields and persist any findings to rce.contradictions (which the GET
    /contradictions routes above read back).

    Idempotent: the SupabaseContradictionStore dedups on
    (case_id, canonical_entity_id, field_key, content_hash), so this is safe to
    call repeatedly — e.g. after a new document is extracted, or as a manual
    HR "re-check". Tenant-scoped via _require_case_access (404 on mismatch).
    """
    _require_case_access(case_id, org_id)
    try:
        case_uuid = UUID(case_id)
    except ValueError:
        # Legacy relocation_cases ids can be non-UUID text; such a case has no
        # rce.cases row to detect against, so there is nothing to do.
        return ContradictionDetectResponse(case_id=case_id, detected=0, contradiction_types=[])
    detected = run_contradiction_detection_for_case(case_uuid)
    return ContradictionDetectResponse(
        case_id=case_id,
        detected=len(detected),
        contradiction_types=sorted({c.type for c in detected}),
    )


@router.get("/behind-schedule")
def get_behind_schedule_cases(
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """[AIQ-378d] Behind-schedule ("case health") cases for this HR company.

    Returns the open ``case_behind_schedule`` proactive alerts scoped to the
    company's own cases (tenant-safe). Each entry carries stage, days_behind,
    expected_date, severity, and the suggested action / draft reminder. Empty
    until the pilot populates case milestones.
    """
    from ..services.case_health_scan import list_behind_cases_for_company

    return {"cases": list_behind_cases_for_company(org_id)}


# ---------------------------------------------------------------------------
# N. POST /{case_id}/employee-briefing  — FRIDAY-005 (AIQ-648)
#    Personalised, citation-grounded relocation briefing for the employee on a
#    case, generated from the company's active policy via Claude Sonnet 4.6
#    (1M-token context). Service + prompts: backend/app/services/briefing.py.
# ---------------------------------------------------------------------------


class BriefingResponse(BaseModel):
    briefing: str
    cost_usd: float
    latency_ms: int
    model: str


def _load_active_policy_text(org_id: str) -> Optional[str]:
    """Return the company's active policy as plain text, or None if none exists.

    Primary source is ``policy_documents.raw_text`` (already extracted at intake).
    Fallback: download the PDF from ``storage_path`` and run pdf_bytes_to_text.
    "Active" = most recently uploaded policy document for the company.

    SEAM [FRIDAY-005]: the policy_documents schema (company_id text, storage_path
    text, raw_text text) is confirmed from migrations, but the storage *bucket*
    for storage_path and the precise "active" semantics aren't — both are wrapped
    so a schema mismatch degrades to None (→ 404) rather than a 500.
    """
    row = None
    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT raw_text, storage_path
                    FROM public.policy_documents
                    WHERE company_id = :org
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"org": org_id},
            ).mappings().first()
    except Exception:
        return None
    if not row:
        return None

    raw_text = (row.get("raw_text") or "").strip()
    if raw_text:
        return raw_text

    storage_path = row.get("storage_path")
    if not storage_path:
        return None
    # Fallback: pull the PDF bytes from storage and extract. Best-effort — the
    # service-role client + bucket are flagged as a seam to confirm.
    try:
        from ..services.supabase_client import get_supabase_admin_client
        from ..utils.pdf_to_text import pdf_bytes_to_text_cached

        # TODO [FRIDAY-005]: confirm the storage bucket for policy PDFs. The
        # intake module stores them under a policy bucket; until confirmed we
        # treat storage_path as "<bucket>/<path>" and split on the first slash.
        bucket, _, path = str(storage_path).partition("/")
        pdf_bytes = get_supabase_admin_client().storage.from_(bucket).download(path)
        return pdf_bytes_to_text_cached(pdf_bytes)
    except Exception:
        return None


def _build_employee_for_briefing(case: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map a relocation_cases row → the employee dict briefing.py expects.

    SEAM [FRIDAY-005]: typed case columns (employee_id, origin/dest country, target
    start date) are confirmed; grade / assignment_type / dependants live in the
    untyped ``profile_json`` blob whose exact keys vary, so they're read best-effort
    across a few candidate names and left as gaps ("not provided") when absent —
    which the prompt handles gracefully rather than inventing.
    """
    employee_id = case.get("employee_id") or ""
    if not employee_id:
        return None

    name: Optional[str] = None
    try:
        user = db.get_user_by_id(employee_id)
    except Exception:
        user = None
    if user:
        name = user.get("name") or user.get("email")

    profile = case.get("profile_json")
    if isinstance(profile, str):
        try:
            import json as _json

            profile = _json.loads(profile)
        except Exception:
            profile = {}
    if not isinstance(profile, dict):
        profile = {}

    def pick(*keys: str) -> Optional[Any]:
        for k in keys:
            v = profile.get(k) or case.get(k)
            if v not in (None, "", []):
                return v
        return None

    return {
        "name": name or pick("name", "full_name", "employee_name"),
        "grade": pick("grade", "grade_band", "gradeBand", "seniority", "level"),
        "assignment_type": pick("assignment_type", "assignmentType", "assignment", "move_type"),
        "home_country": pick("origin_country_code", "home_country", "origin", "origin_country"),
        "destination": pick("dest_country_code", "destination_country", "destination", "host_country") or case.get("corridor"),
        "departure_date": (str(case["target_start_date"]) if case.get("target_start_date") else pick("departure_date", "target_move_date", "move_date")),
        "dependants": pick("dependants", "dependents", "family"),
    }


@router.post("/{case_id}/employee-briefing", response_model=BriefingResponse)
def generate_case_employee_briefing(
    case_id: str,
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> BriefingResponse:
    """Generate a personalised, citation-grounded relocation briefing for the
    employee on this case, from the company's active policy (Sonnet 4.6, 1M ctx).

    401 if not an HR/admin; 404 if the case isn't in the caller's company (RLS) or
    no active policy exists; 400 if no employee is linked; 422 if the policy PDF
    can't be parsed; 502 on an Anthropic API error.
    """
    from ..services.briefing import BriefingError, generate_employee_briefing

    case = _require_case_access(case_id, org_id)  # 404 on RLS mismatch

    employee = _build_employee_for_briefing(case)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No employee assigned to this case")

    policy_text = _load_active_policy_text(org_id)
    if not policy_text:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active policy document found")

    try:
        result = generate_employee_briefing(policy_text, employee)
    except BriefingError as exc:
        # Don't leak a raw stack trace; surface a bounded message.
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Briefing generation failed: {exc}") from exc

    return BriefingResponse(**result)
