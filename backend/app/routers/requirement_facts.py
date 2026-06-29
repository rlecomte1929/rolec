"""[AIQ-1091 / P4-02] Requirement-facts extraction endpoint.

Wires the P4-01 pure extractor (`extract_requirement_facts`) to a REST API and persists the
results to `requirement_fact_candidates` with status='pending', for admin review (P4-03).
Admin-only. The persist is best-effort (a missing/un-applied table never fails the request).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import require_admin
from ...database import db
from ..services.requirement_fact_extractor import RequirementFact, extract_requirement_facts

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["requirement-facts"])


class RequirementFactsExtractRequest(BaseModel):
    source_url: str = Field(..., description="Official source URL to extract requirement facts from.")
    corridor: str = Field("", description="Corridor context, e.g. 'IN-DE'.")
    requirement_type_hint: Optional[str] = Field(
        None, description="Optional filter: only return facts of this requirement_type."
    )


def _serialize(f: RequirementFact) -> Dict[str, Any]:
    return {
        "text": f.text,
        "requirement_type": f.requirement_type,
        "corridor": f.corridor,
        "confidence_score": f.confidence_score,
        "source_quote": f.source_quote,
        "source_url": f.source_url,
        "extraction_method": f.extraction_method,
    }


@router.post("/requirement-facts/extract")
async def extract_requirement_facts_endpoint(
    body: RequirementFactsExtractRequest,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Extract requirement facts from a URL (P4-01) and persist them as pending candidates (P4-02)."""
    url = (body.source_url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="source_url is required")

    try:
        facts = await extract_requirement_facts(url, corridor=(body.corridor or "").strip())
    except Exception as exc:  # upstream fetch / LLM error
        log.warning("requirement-facts extract failed corridor=%s err=%s", body.corridor, exc)
        raise HTTPException(status_code=502, detail="extraction_failed")

    hint = (body.requirement_type_hint or "").strip().lower()
    if hint:
        facts = [f for f in facts if f.requirement_type == hint]

    pending = 0
    for f in facts:
        try:
            with db.engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO requirement_fact_candidates "
                        "(source_url, corridor, requirement_type, fact_text, confidence_score, "
                        " source_quote, extraction_method, status) "
                        "VALUES (:url, :corridor, :rtype, :ftext, :conf, :quote, :method, 'pending')"
                    ),
                    {
                        "url": f.source_url,
                        "corridor": f.corridor or None,
                        "rtype": f.requirement_type,
                        "ftext": f.text,
                        "conf": f.confidence_score,
                        "quote": f.source_quote or None,
                        "method": f.extraction_method,
                    },
                )
            pending += 1
        except Exception as exc:
            log.warning("requirement_fact_candidates insert skipped err=%s", exc)

    return {"extracted": len(facts), "pending": pending, "facts": [_serialize(f) for f in facts]}
