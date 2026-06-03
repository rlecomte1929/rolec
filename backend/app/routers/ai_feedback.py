"""
AI human-feedback API (Parker Step E).

A single endpoint the Notion review skill calls when a reviewer approves /
rejects / edits an AI output. The verdict lands in ``ai_human_feedback`` attributed
to the prompt-registry version + canary arm that served the request (derived from
the trace). Idempotent on ``(trace_session_id, reviewer_user_id)``.

  POST /api/ai/feedback   (session-token auth — any authenticated reviewer)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth_deps import get_current_user
from ..services import ai_feedback_service

router = APIRouter(prefix="/api/ai", tags=["ai-feedback"])
logger = logging.getLogger(__name__)


class FeedbackCreate(BaseModel):
    trace_session_id: str = Field(..., min_length=1)
    verdict: str = Field(..., description="approved | rejected | edited")
    edited_output_json: Optional[Dict[str, Any]] = None
    comment: Optional[str] = None


@router.post("/feedback", status_code=201)
def submit_feedback(
    body: FeedbackCreate, user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Record a human review verdict (idempotent per trace + reviewer)."""
    reviewer_user_id = str(user.get("id") or user.get("user_id") or "")
    if not reviewer_user_id:
        raise HTTPException(status_code=401, detail="No reviewer identity")
    try:
        return ai_feedback_service.record_feedback(
            trace_session_id=body.trace_session_id,
            reviewer_user_id=reviewer_user_id,
            verdict=body.verdict,
            edited_output_json=body.edited_output_json,
            comment=body.comment,
        )
    except ai_feedback_service.UnknownTraceError:
        raise HTTPException(status_code=404, detail="Unknown trace_session_id")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
