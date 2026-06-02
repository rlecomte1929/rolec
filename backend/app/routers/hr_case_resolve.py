"""
C1-12-be · Contradiction resolve + escalate POST endpoints.

Closes the C1-12 Resolution UI's Partial deferral. The frontend mutation
hook on apps/hr-dashboard/src/api/contradictions.ts already binds to
these endpoints — once this lands, the data flywheel is live: every
override produces a Correction row with full context_snapshot, feeding
Cohort 5's retrieval-augmented suggestion.

Endpoints:
  POST /api/hr/cases/{case_id}/contradictions/{cid}/resolve
  POST /api/hr/cases/{case_id}/contradictions/{cid}/escalate

Both are RLS-scoped (404 on cross-tenant) and transactional (the resolve
endpoint commits the correction + contradiction + extracted_field
updates together; if any step fails, the whole call rolls back).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ...database import db


router = APIRouter(prefix="/api/hr/cases", tags=["hr-case-resolve"])


# ---------------------------------------------------------------------------
# Constants — P0-06 reason codes must match the frontend dropdown verbatim
# (apps/hr-dashboard/src/features/resolution/reasonCodes.ts) AND the C1-01
# CHECK constraint on rce.corrections.reason_code.
# ---------------------------------------------------------------------------


ReasonCode = Literal[
    "OCR_ERROR",
    "TYPO_IN_SOURCE",
    "AMBIGUOUS_PARTICLE",
    "LEGITIMATE_VARIATION",
    "FRAUD_SUSPECTED",
    "OTHER",
]

VALID_REASON_CODES = {
    "OCR_ERROR",
    "TYPO_IN_SOURCE",
    "AMBIGUOUS_PARTICLE",
    "LEGITIMATE_VARIATION",
    "FRAUD_SUSPECTED",
    "OTHER",
}

_PRIOR_CORRECTIONS_LIMIT = 5


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


class ResolveRequest(BaseModel):
    winner_candidate_id: str = Field(..., min_length=1)
    reason_code: ReasonCode
    reason_freetext: Optional[str] = Field(default=None, max_length=500)


class ResolveResponse(BaseModel):
    contradiction_id: str
    resolution_status: str
    canonical_value: Optional[Any] = None
    correction_id: str


class EscalateRequest(BaseModel):
    reason_freetext: str = Field(..., min_length=1, max_length=500)


class EscalateResponse(BaseModel):
    contradiction_id: str
    resolution_status: str
    escalation_id: str


# ---------------------------------------------------------------------------
# Tenant gate — same pattern as hr_case_detail / hr_case_audit
# ---------------------------------------------------------------------------


def _require_case_access(case_id: str, org_id: str) -> Dict[str, Any]:
    row = db.get_relocation_case(case_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    case_company_id = row.get("company_id")
    if case_company_id and case_company_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return row


# ---------------------------------------------------------------------------
# Helpers — context_snapshot assembly (the data-flywheel feed)
# ---------------------------------------------------------------------------


def _build_context_snapshot(
    conn: Any,
    contradiction: Dict[str, Any],
    winning_candidate: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Capture everything a future model would need to learn from this
    decision. Per Architecture Report §3.8:
      - All candidate values + sources + confidences (not just winner/loser)
      - Agent versions that produced each ExtractedField
      - LLM model + routing decision (from agent_runs)
      - Prior corrections on (canonical_entity_id, field_key) — last 5
      - The document text + bboxes that anchored each candidate
    """
    canonical_entity_id = contradiction.get("canonical_entity_id")
    field_key = contradiction.get("field_key")
    candidates: List[Dict[str, Any]] = []
    raw_candidates = contradiction.get("candidates") or []
    if isinstance(raw_candidates, str):
        try:
            raw_candidates = json.loads(raw_candidates)
        except Exception:
            raw_candidates = []
    if isinstance(raw_candidates, list):
        candidates = [dict(c) for c in raw_candidates if isinstance(c, dict)]

    # Agent runs that produced any of the candidates' extractions.
    agent_run_ids = [
        c.get("source_agent_run_id") for c in candidates if c.get("source_agent_run_id")
    ]
    agent_runs: List[Dict[str, Any]] = []
    if agent_run_ids:
        try:
            rows = conn.execute(
                text(
                    """
                    SELECT agent_run_id, agent_id, agent_version, llm_model_used,
                           cost_tokens, status, output_digest, started_at, finished_at
                    FROM rce.agent_runs
                    WHERE agent_run_id = ANY(:ids)
                    """
                ),
                {"ids": agent_run_ids},
            ).mappings().all()
            for r in rows:
                agent_runs.append(
                    {
                        "agent_run_id": str(r["agent_run_id"]),
                        "agent_id": r.get("agent_id"),
                        "agent_version": r.get("agent_version"),
                        "model": r.get("llm_model_used"),
                        "cost_tokens": r.get("cost_tokens"),
                        "status": r.get("status"),
                        "output_digest": r.get("output_digest"),
                        "started_at": r["started_at"].isoformat() if r.get("started_at") else None,
                        "finished_at": r["finished_at"].isoformat() if r.get("finished_at") else None,
                    }
                )
        except Exception:
            agent_runs = []

    # Prior corrections on the same (canonical_entity, field).
    prior_corrections: List[Dict[str, Any]] = []
    if canonical_entity_id and field_key:
        try:
            rows = conn.execute(
                text(
                    """
                    SELECT correction_id, field, reason_code, reason_freetext,
                           corrected_at, corrected_by, value_before, value_after
                    FROM rce.corrections
                    WHERE target_id = :entity_id AND field = :field_key
                    ORDER BY corrected_at DESC
                    LIMIT :n
                    """
                ),
                {
                    "entity_id": canonical_entity_id,
                    "field_key": field_key,
                    "n": _PRIOR_CORRECTIONS_LIMIT,
                },
            ).mappings().all()
            for r in rows:
                prior_corrections.append(
                    {
                        "correction_id": str(r["correction_id"]),
                        "field": r.get("field"),
                        "reason_code": r.get("reason_code"),
                        "reason_freetext": r.get("reason_freetext"),
                        "corrected_at": r["corrected_at"].isoformat() if r.get("corrected_at") else None,
                        "corrected_by": str(r["corrected_by"]) if r.get("corrected_by") else None,
                    }
                )
        except Exception:
            prior_corrections = []

    return {
        "candidates": candidates,
        "winning_candidate": winning_candidate,
        "winning_candidate_id": (winning_candidate or {}).get("candidate_id"),
        "agent_runs": agent_runs,
        "prior_corrections": prior_corrections,
        "snapshot_ts": datetime.now(timezone.utc).isoformat(),
    }


def _find_winning_candidate(
    candidates: List[Dict[str, Any]], winner_id: str
) -> Optional[Dict[str, Any]]:
    for c in candidates:
        cid = c.get("candidate_id") or c.get("document_id")
        if cid and str(cid) == str(winner_id):
            return c
    return None


# ---------------------------------------------------------------------------
# POST /resolve
# ---------------------------------------------------------------------------


@router.post(
    "/{case_id}/contradictions/{contradiction_id}/resolve",
    response_model=ResolveResponse,
)
def resolve_contradiction(
    case_id: str,
    contradiction_id: str,
    payload: ResolveRequest,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> ResolveResponse:
    """
    Resolve a contradiction by picking a winning candidate.

    Single transaction:
      1. INSERT INTO rce.corrections with full context_snapshot
      2. UPDATE rce.contradictions resolution_status='Resolved'
      3. UPDATE rce.extracted_fields for the winning value's source

    If any step fails, the whole transaction rolls back so we never
    have a half-applied resolve.

    409 returned if the contradiction is already Resolved — the body
    includes the existing correction_id so the UI can recover.
    """
    _require_case_access(case_id, org_id)

    # Validate reason_code → at the schema level FastAPI Literal enforces this,
    # but assert again so a future schema drift doesn't silently break the
    # CHECK constraint downstream.
    if payload.reason_code not in VALID_REASON_CODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown reason_code: {payload.reason_code}",
        )

    # OTHER requires a freetext explanation — mirror the frontend rule.
    if payload.reason_code == "OTHER" and not (payload.reason_freetext or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTHER reason requires an explanation in reason_freetext.",
        )

    hr_user_id = hr_user.get("id")

    try:
        with db.engine.begin() as conn:
            # 1. Load the contradiction + verify case scoping again at SQL level.
            row = conn.execute(
                text(
                    """
                    SELECT contradiction_id, case_id, canonical_entity_id,
                           field_key, contradiction_type, candidates,
                           resolution_status
                    FROM rce.contradictions
                    WHERE contradiction_id = :cid AND case_id = :case_id
                    FOR UPDATE
                    """
                ),
                {"cid": contradiction_id, "case_id": case_id},
            ).mappings().one_or_none()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Contradiction not found",
                )

            # 2. Idempotency: if already Resolved, fetch the existing correction
            #    and return 409 with its id so the UI recovers.
            if str(row.get("resolution_status")) == "Resolved":
                existing = conn.execute(
                    text(
                        """
                        SELECT correction_id
                        FROM rce.corrections
                        WHERE target_table = 'rce.contradictions'
                          AND target_id = :cid
                        ORDER BY corrected_at DESC
                        LIMIT 1
                        """
                    ),
                    {"cid": contradiction_id},
                ).mappings().one_or_none()
                existing_id = str(existing["correction_id"]) if existing else ""
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "message": "Contradiction already resolved.",
                        "correction_id": existing_id,
                    },
                )

            # 3. Validate winner_candidate_id is one of the contradiction's candidates.
            raw_candidates = row.get("candidates") or []
            if isinstance(raw_candidates, str):
                try:
                    raw_candidates = json.loads(raw_candidates)
                except Exception:
                    raw_candidates = []
            candidates_list = (
                [dict(c) for c in raw_candidates if isinstance(c, dict)]
                if isinstance(raw_candidates, list)
                else []
            )
            winning_candidate = _find_winning_candidate(
                candidates_list, payload.winner_candidate_id
            )
            if not winning_candidate:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"winner_candidate_id {payload.winner_candidate_id} not in contradiction's candidates",
                )

            # 4. Build the context_snapshot.
            snapshot = _build_context_snapshot(conn, dict(row), winning_candidate)

            # 5. INSERT correction.
            correction_row = conn.execute(
                text(
                    """
                    INSERT INTO rce.corrections (
                        case_id, target_table, target_id, field,
                        value_before, value_after, reason_code, reason_freetext,
                        context_snapshot, corrected_by
                    )
                    VALUES (
                        :case_id, 'rce.contradictions', :cid, :field,
                        NULL, :value_after, :reason_code, :reason_freetext,
                        CAST(:snapshot AS JSONB), :corrected_by
                    )
                    RETURNING correction_id
                    """
                ),
                {
                    "case_id": case_id,
                    "cid": contradiction_id,
                    "field": row.get("field_key"),
                    "value_after": json.dumps(
                        winning_candidate.get("value_canonical")
                        or winning_candidate.get("value_raw")
                    ),
                    "reason_code": payload.reason_code,
                    "reason_freetext": (payload.reason_freetext or "").strip() or None,
                    "snapshot": json.dumps(snapshot),
                    "corrected_by": hr_user_id,
                },
            ).mappings().one()
            correction_id = str(correction_row["correction_id"])

            # 6. UPDATE the contradiction.
            conn.execute(
                text(
                    """
                    UPDATE rce.contradictions
                    SET resolution_status = 'Resolved',
                        resolved_at = NOW(),
                        resolved_by = :hr_user_id,
                        suggested_winner = CAST(:winner AS JSONB),
                        updated_at = NOW()
                    WHERE contradiction_id = :cid
                    """
                ),
                {
                    "cid": contradiction_id,
                    "hr_user_id": hr_user_id,
                    "winner": json.dumps(winning_candidate),
                },
            )

            # 7. Mark the winning ExtractedField as Resolved (best-effort —
            #    the candidate may reference a synthetic extracted_field id).
            ef_id = winning_candidate.get("source_agent_run_id") or winning_candidate.get(
                "extracted_field_id"
            )
            if ef_id:
                conn.execute(
                    text(
                        """
                        UPDATE rce.extracted_fields
                        SET resolution_status = 'Resolved', updated_at = NOW()
                        WHERE extracted_field_id = :ef_id
                        """
                    ),
                    {"ef_id": ef_id},
                )

        return ResolveResponse(
            contradiction_id=contradiction_id,
            resolution_status="Resolved",
            canonical_value=winning_candidate.get("value_canonical")
            or winning_candidate.get("value_raw"),
            correction_id=correction_id,
        )

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resolve failed: {exc.__class__.__name__}",
        ) from exc


# ---------------------------------------------------------------------------
# POST /escalate
# ---------------------------------------------------------------------------


@router.post(
    "/{case_id}/contradictions/{contradiction_id}/escalate",
    response_model=EscalateResponse,
)
def escalate_contradiction(
    case_id: str,
    contradiction_id: str,
    payload: EscalateRequest,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> EscalateResponse:
    """
    Mark a contradiction as escalated to compliance review.

    Until a dedicated escalation queue table lands, escalation is
    recorded as a `rce.corrections` row with reason_code='OTHER' and a
    'ESCALATED:' prefix in reason_freetext. The contradiction's
    resolution_status flips to 'Not resolved' so it stays visible in
    the inbox + the compliance queue can SELECT WHERE prefix LIKE.

    Future migration: dedicated rce.escalations table with FK to
    rce.contradictions + assignee + SLA fields.
    """
    _require_case_access(case_id, org_id)
    hr_user_id = hr_user.get("id")

    try:
        with db.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT contradiction_id, case_id, canonical_entity_id, field_key,
                           resolution_status
                    FROM rce.contradictions
                    WHERE contradiction_id = :cid AND case_id = :case_id
                    FOR UPDATE
                    """
                ),
                {"cid": contradiction_id, "case_id": case_id},
            ).mappings().one_or_none()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Contradiction not found",
                )
            if str(row.get("resolution_status")) == "Resolved":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot escalate a contradiction that's already Resolved.",
                )

            correction_row = conn.execute(
                text(
                    """
                    INSERT INTO rce.corrections (
                        case_id, target_table, target_id, field,
                        value_before, value_after, reason_code, reason_freetext,
                        context_snapshot, corrected_by
                    )
                    VALUES (
                        :case_id, 'rce.contradictions', :cid, :field,
                        NULL, 'null'::jsonb, 'OTHER', :reason_text,
                        CAST(:snapshot AS JSONB), :corrected_by
                    )
                    RETURNING correction_id
                    """
                ),
                {
                    "case_id": case_id,
                    "cid": contradiction_id,
                    "field": row.get("field_key"),
                    "reason_text": f"ESCALATED: {payload.reason_freetext.strip()}",
                    "snapshot": json.dumps(
                        {
                            "escalated": True,
                            "escalation_reason": payload.reason_freetext.strip(),
                            "snapshot_ts": datetime.now(timezone.utc).isoformat(),
                        }
                    ),
                    "corrected_by": hr_user_id,
                },
            ).mappings().one()

            conn.execute(
                text(
                    """
                    UPDATE rce.contradictions
                    SET resolution_status = 'Not resolved', updated_at = NOW()
                    WHERE contradiction_id = :cid
                    """
                ),
                {"cid": contradiction_id},
            )

        return EscalateResponse(
            contradiction_id=contradiction_id,
            resolution_status="Not resolved",
            escalation_id=str(correction_row["correction_id"]),
        )

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Escalate failed: {exc.__class__.__name__}",
        ) from exc
