"""
privacy_consents.py — GDPR Art. 13 privacy-notice acknowledgement.

Two endpoints:
  POST /api/privacy/consents              record an acknowledgement
  GET  /api/privacy/consents?notice_version=...   has the caller acknowledged?

Distinct from immigration_intake_consent.py (per-purpose, per-case lawful-basis
consent). This logs the act of being shown the Art. 13 transparency notice at a
point of collection, keyed by notice_version so a material copy change triggers
re-acknowledgement on the next collection surface.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_current_user
from ...database import db

router = APIRouter(prefix="/api/privacy", tags=["privacy-consents"])


class AcknowledgeBody(BaseModel):
    notice_version: str
    context: Optional[str] = None  # 'onboarding' | 'task_submission'


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/consents", status_code=201)
def record_acknowledgement(
    body: AcknowledgeBody,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Record that the authenticated user acknowledged the privacy notice.

    Idempotent for a given (user_id, notice_version): if a row already exists
    the existing acknowledgement is returned instead of writing a duplicate —
    this absorbs the network-retry case from the React component.
    """
    user_id = current_user["id"]
    now = _now_iso()

    with db.engine.begin() as conn:
        existing = conn.execute(
            text("""
                SELECT id, acknowledged_at
                FROM public.privacy_consents
                WHERE user_id = :user_id AND notice_version = :version
                ORDER BY created_at ASC
                LIMIT 1
            """),
            {"user_id": user_id, "version": body.notice_version},
        ).mappings().first()

        if existing:
            return {
                "consent_id": existing["id"],
                "notice_version": body.notice_version,
                "acknowledged_at": existing["acknowledged_at"],
                "already_acknowledged": True,
            }

        consent_id = str(uuid.uuid4())
        conn.execute(
            text("""
                INSERT INTO public.privacy_consents
                    (id, user_id, notice_version, acknowledged_at, context,
                     ip_address, user_agent)
                VALUES
                    (:id, :user_id, :version, :now, :context, :ip, :ua)
            """),
            {
                "id": consent_id,
                "user_id": user_id,
                "version": body.notice_version,
                "now": now,
                "context": body.context,
                "ip": request.client.host if request.client else None,
                "ua": request.headers.get("user-agent"),
            },
        )

    return {
        "consent_id": consent_id,
        "notice_version": body.notice_version,
        "acknowledged_at": now,
        "already_acknowledged": False,
    }


@router.get("/consents")
def get_acknowledgement_status(
    notice_version: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Has the authenticated user acknowledged this notice_version?

    The frontend uses this to decide whether to re-present the notice: a bumped
    notice_version has no row → acknowledged=False → the gate re-appears.
    """
    user_id = current_user["id"]

    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT id, acknowledged_at
                FROM public.privacy_consents
                WHERE user_id = :user_id AND notice_version = :version
                ORDER BY created_at ASC
                LIMIT 1
            """),
            {"user_id": user_id, "version": notice_version},
        ).mappings().first()

    return {
        "notice_version": notice_version,
        "acknowledged": row is not None,
        "acknowledged_at": row["acknowledged_at"] if row else None,
    }
