"""[AIQ-1091 / P4-02] Requirement-facts extraction endpoint.

Wires the P4-01 pure extractor (`extract_requirement_facts`) to a REST API and persists the
results to `requirement_fact_candidates` with status='pending', for admin review (P4-03).
Admin-only. The persist is best-effort (a missing/un-applied table never fails the request).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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


# ── P4-03 (AIQ-1092): admin review — list + approve/reject ───────────────────

_CANDIDATE_COLUMNS = (
    "id, created_at, source_url, corridor, requirement_type, fact_text, "
    "confidence_score, source_quote, extraction_method, status, reviewed_by, reviewed_at"
)


class RequirementFactReview(BaseModel):
    status: Literal["approved", "rejected"]


def _serialize_candidate(row: Any) -> Dict[str, Any]:
    """Normalise a requirement_fact_candidates row (Postgres or SQLite) to JSON-safe types."""
    def _iso(v: Any) -> Optional[str]:
        return v.isoformat() if hasattr(v, "isoformat") else (str(v) if v is not None else None)

    conf = row["confidence_score"]
    return {
        "id": str(row["id"]),
        "created_at": _iso(row["created_at"]),
        "source_url": row["source_url"],
        "corridor": row["corridor"],
        "requirement_type": row["requirement_type"],
        "fact_text": row["fact_text"],
        "confidence_score": float(conf) if conf is not None else None,
        "source_quote": row["source_quote"],
        "extraction_method": row["extraction_method"],
        "status": row["status"],
        "reviewed_by": (str(row["reviewed_by"]) if row["reviewed_by"] is not None else None),
        "reviewed_at": _iso(row["reviewed_at"]),
    }


@router.get("/requirement-facts")
def list_requirement_facts(
    status: str = Query("pending"),
    limit: int = Query(100, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_admin),
) -> List[Dict[str, Any]]:
    """List extracted requirement-fact candidates by status (default: pending), newest first."""
    with db.engine.connect() as conn:
        rows = conn.execute(
            text(
                f"SELECT {_CANDIDATE_COLUMNS} FROM requirement_fact_candidates "
                "WHERE status = :status ORDER BY created_at DESC LIMIT :limit"
            ),
            {"status": status, "limit": limit},
        ).mappings().all()
    return [_serialize_candidate(r) for r in rows]


@router.patch("/requirement-facts/{fact_id}")
def review_requirement_fact(
    fact_id: str,
    body: RequirementFactReview,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Approve or reject one extracted requirement fact (records reviewer + timestamp)."""
    now = datetime.now(timezone.utc).isoformat()
    with db.engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM requirement_fact_candidates WHERE id = :id"),
            {"id": fact_id},
        ).first()
        if not existing:
            raise HTTPException(status_code=404, detail="requirement fact not found")

        conn.execute(
            text(
                "UPDATE requirement_fact_candidates "
                "SET status = :status, reviewed_by = :uid, reviewed_at = :now WHERE id = :id"
            ),
            {"status": body.status, "uid": str(user.get("id")), "now": now, "id": fact_id},
        )
        row = conn.execute(
            text(f"SELECT {_CANDIDATE_COLUMNS} FROM requirement_fact_candidates WHERE id = :id"),
            {"id": fact_id},
        ).mappings().first()
    return _serialize_candidate(row)
