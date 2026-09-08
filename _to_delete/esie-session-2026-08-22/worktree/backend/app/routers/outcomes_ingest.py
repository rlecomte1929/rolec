"""
outcomes_ingest.py — internal trigger for the outcome flywheel (P1-07d / AIQ-687).

  POST /api/internal/outcomes/ingest   {case_id}

Service-role-only (admin) entry point to (re)compute and persist one case's
anonymized outcome. The work is done by outcome_extractor.extract_and_persist
(AIQ-685): it computes → consent-gates (AIQ-686) → idempotently upserts a single
case_outcomes row per case (keyed on case_ref_hash), so repeated calls never
duplicate. Mirrors the sibling /api/internal/* admin routers (rag_roadmap,
specialist_review).
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth_deps import require_admin
from ..db import SessionLocal
from ..services.outcome_extractor import extract_and_persist

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal/outcomes", tags=["outcomes-ingest"])


class IngestBody(BaseModel):
    case_id: str


@router.post("/ingest")
def ingest_outcome(
    body: IngestBody,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Trigger outcome extraction for one case. Idempotent + consent-gated.

    Returns ``ingested: true`` if a row was written/updated, ``false`` if it was
    skipped for lack of consent (a valid 200, not an error). 404 if the case
    does not exist. Public/anon callers are rejected by ``require_admin`` (403).
    """
    with SessionLocal() as session:
        try:
            data = extract_and_persist(session, body.case_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Case not found")
        session.commit()

    return {"case_id": body.case_id, "ingested": data is not None}
