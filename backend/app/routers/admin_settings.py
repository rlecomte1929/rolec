"""Admin AI-governance controls panel (Task 4).

GET  /api/admin/ai-controls               → resolved value + source per key
POST /api/admin/ai-controls               → write a new value (gated, audited)
POST /api/admin/ai-controls/kill/{feature} → force safe default "0"

All routes require admin. Dual-registered in both backend/main.py and
backend/app/main.py (CLAUDE.md dual-layer rule).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Generator, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..auth_deps import require_admin
from ..db import SessionLocal
from ..services.admin_audit import record_admin_event
from ..services.platform_settings import set_setting

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin-ai-controls"])

# ---------------------------------------------------------------------------
# Allowlist of known AI-governance keys → env-var name → default value
# ---------------------------------------------------------------------------
KNOWN_KEYS: Dict[str, str] = {
    "policy_rag_groundedness_gate": "POLICY_RAG_GROUNDEDNESS_GATE",
    "policy_rag_groundedness_min_score": "POLICY_RAG_GROUNDEDNESS_MIN_SCORE",
    "policy_rag_rerank": "POLICY_RAG_RERANK",
    "supplier_learned_weights": "SUPPLIER_LEARNED_WEIGHTS",
}

DEFAULTS: Dict[str, str] = {
    "policy_rag_groundedness_gate": "0",
    "policy_rag_groundedness_min_score": "0.5",
    "policy_rag_rerank": "0",
    "supplier_learned_weights": "0",
}


def _get_db() -> Generator:
    """Yield a SQLAlchemy session; commit on success, rollback on error."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _resolve_entry(key: str, env_var: str, default: str, db: Session) -> Dict[str, Any]:
    """Return {key, value, source} for one setting (env → db → default)."""
    env_val = os.environ.get(env_var)
    if env_val is not None:
        return {"key": key, "value": env_val, "source": "env"}
    try:
        row = db.execute(
            text("SELECT value_json FROM platform_settings WHERE key = :key"), {"key": key}
        ).first()
        if row is not None:
            raw = row[0]
            try:
                val = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                val = raw
            return {"key": key, "value": str(val) if val is not None else default, "source": "db"}
    except Exception as exc:
        log.debug("_resolve_entry(%r) db look-up failed: %s", key, exc)
    return {"key": key, "value": default, "source": "default"}


class AiControlUpdate(BaseModel):
    key: str = Field(..., min_length=1)
    value: str = Field(...)
    reason: str = Field(..., min_length=1, max_length=512)


@router.get("/ai-controls")
def list_ai_controls(
    db: Session = Depends(_get_db),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Return each known AI-governance setting with its resolved value and source."""
    controls: List[Dict[str, Any]] = [
        _resolve_entry(key, env_var, DEFAULTS[key], db)
        for key, env_var in KNOWN_KEYS.items()
    ]
    return {"controls": controls}


@router.post("/ai-controls")
def set_ai_control(
    body: AiControlUpdate,
    db: Session = Depends(_get_db),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Persist a new value for a known AI-governance setting (validated + audited)."""
    if body.key not in KNOWN_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown key: {body.key!r}. Allowed: {sorted(KNOWN_KEYS)}",
        )
    actor_id = str(user.get("id") or user.get("user_id") or "unknown")
    set_setting(db, body.key, body.value, actor_id=actor_id)
    record_admin_event(
        db,
        actor_id=actor_id,
        event="ai_setting_changed",
        entity="platform_settings",
        entity_id=body.key,
        detail={"key": body.key, "value": body.value, "reason": body.reason},
    )
    return {"key": body.key, "value": body.value, "source": "db"}


@router.post("/ai-controls/kill/{feature}")
def kill_ai_feature(
    feature: str,
    db: Session = Depends(_get_db),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Force a known AI-governance flag to its safe default ("0") — the kill-switch."""
    if feature not in KNOWN_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown feature: {feature!r}. Allowed: {sorted(KNOWN_KEYS)}",
        )
    actor_id = str(user.get("id") or user.get("user_id") or "unknown")
    set_setting(db, feature, "0", actor_id=actor_id)
    record_admin_event(
        db,
        actor_id=actor_id,
        event="ai_setting_changed",
        entity="platform_settings",
        entity_id=feature,
        detail={"key": feature, "value": "0", "reason": "kill-switch"},
    )
    return {"key": feature, "value": "0", "source": "db"}
