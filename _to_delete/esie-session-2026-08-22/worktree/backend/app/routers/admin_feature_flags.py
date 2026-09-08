"""
Feature-flag console (admin-only) — CRUD over the DB-backed `feature_flags` /
`feature_flag_accounts` tables so flags can be toggled without a redeploy. The table,
RLS, ORM, and resolver already exist (P2-01a); this adds the missing admin surface.
Every write is audit-logged.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func

from ..auth_deps import require_admin
from ..db import SessionLocal
from ..models import FeatureFlag, FeatureFlagAccount
from ...database import db

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-feature-flags"])


def _audit(admin: Dict[str, Any], event: str, key: str, meta: Dict[str, Any]) -> None:
    try:
        db.log_audit(
            actor_user_id=str(admin.get("id") or ""), action_type=event,
            target_type="feature_flag", target_id=key, reason="feature-flag console", metadata=meta,
        )
    except Exception:  # audit is best-effort
        log.warning("audit: %s %s", event, key)


class FlagBody(BaseModel):
    key: str
    enabled: bool = False
    description: Optional[str] = None


class FlagPatch(BaseModel):
    enabled: Optional[bool] = None
    description: Optional[str] = None


class AccountBody(BaseModel):
    account_id: str


@router.get("/feature-flags")
def list_flags(_admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    with SessionLocal() as s:
        flags = s.query(FeatureFlag).order_by(FeatureFlag.key).all()
        counts = dict(
            s.query(FeatureFlagAccount.flag_key, func.count()).group_by(FeatureFlagAccount.flag_key).all()
        )
        items: List[Dict[str, Any]] = [
            {
                "key": f.key,
                "enabled": bool(f.enabled),
                "description": f.description,
                "account_count": int(counts.get(f.key, 0)),
                "updated_at": f.updated_at.isoformat() if f.updated_at else None,
            }
            for f in flags
        ]
    return {"items": items}


@router.post("/feature-flags")
def upsert_flag(body: FlagBody, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    key = (body.key or "").strip()
    if not key:
        raise HTTPException(status_code=422, detail="key is required")
    with SessionLocal() as s:
        flag = s.get(FeatureFlag, key)
        if flag is None:
            s.add(FeatureFlag(key=key, enabled=body.enabled, description=body.description))
        else:
            flag.enabled = body.enabled
            if body.description is not None:
                flag.description = body.description
        s.commit()
    _audit(admin, "feature_flag_upsert", key, {"enabled": body.enabled})
    return {"ok": True, "key": key}


@router.patch("/feature-flags/{key}")
def patch_flag(key: str, body: FlagPatch, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    with SessionLocal() as s:
        flag = s.get(FeatureFlag, key)
        if flag is None:
            raise HTTPException(status_code=404, detail="flag not found")
        if body.enabled is not None:
            flag.enabled = body.enabled
        if body.description is not None:
            flag.description = body.description
        s.commit()
    _audit(admin, "feature_flag_update", key, {"enabled": body.enabled})
    return {"ok": True, "key": key}


@router.post("/feature-flags/{key}/accounts")
def add_account(key: str, body: AccountBody, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    account_id = (body.account_id or "").strip()
    if not account_id:
        raise HTTPException(status_code=422, detail="account_id is required")
    with SessionLocal() as s:
        if s.get(FeatureFlag, key) is None:
            raise HTTPException(status_code=404, detail="flag not found")
        if s.get(FeatureFlagAccount, (key, account_id)) is None:
            s.add(FeatureFlagAccount(flag_key=key, account_id=account_id))
            s.commit()
    _audit(admin, "feature_flag_account_add", key, {"account_id": account_id})
    return {"ok": True}


@router.delete("/feature-flags/{key}/accounts/{account_id}")
def remove_account(key: str, account_id: str, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    with SessionLocal() as s:
        row = s.get(FeatureFlagAccount, (key, account_id))
        if row is not None:
            s.delete(row)
            s.commit()
    _audit(admin, "feature_flag_account_remove", key, {"account_id": account_id})
    return {"ok": True}
