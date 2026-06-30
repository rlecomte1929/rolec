"""End-user policy-answer helpfulness API (WS-E).

A single endpoint the employee UI calls when a user marks a policy answer helpful
or not ("was this answer helpful?"). The vote lands in
``policy_answer_helpfulness`` keyed to the answer's trace; the company tenant is
derived from the trace. Idempotent on ``(trace_session_id, user_id)``.

  POST /api/policy-assistant/helpfulness   (session-token auth — any authed user)

This is the END-USER sibling of /api/ai/feedback (which is INTERNAL-REVIEWER only).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth_deps import get_current_user
from ..services import policy_helpfulness_service

router = APIRouter(prefix="/api/policy-assistant", tags=["policy-helpfulness"])
logger = logging.getLogger(__name__)


class HelpfulnessCreate(BaseModel):
    trace_session_id: str = Field(..., min_length=1)
    helpful: bool = Field(..., description="True = thumbs up, False = thumbs down")
    comment: Optional[str] = None


@router.post("/helpfulness", status_code=201)
def submit_helpfulness(
    body: HelpfulnessCreate, user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Record an end-user helpfulness vote (idempotent per answer + user)."""
    user_id = str(user.get("id") or user.get("user_id") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="No user identity")
    try:
        return policy_helpfulness_service.record_helpfulness(
            trace_session_id=body.trace_session_id,
            user_id=user_id,
            helpful=body.helpful,
            comment=body.comment,
        )
    except policy_helpfulness_service.UnknownTraceError:
        raise HTTPException(status_code=404, detail="Unknown trace_session_id")
