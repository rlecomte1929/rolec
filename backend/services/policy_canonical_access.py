"""
Helpers for canonical policy tenant scoping and RBAC.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException

from ..database import Database


def resolve_user_company_id(user: Dict[str, Any], db: Database) -> str:
    profile = db.get_profile_record(str(user.get("id") or "")) or {}
    company_id = str(profile.get("company_id") or user.get("company") or "").strip()
    if not company_id:
        raise HTTPException(status_code=400, detail="User is not linked to a company")
    return company_id


def ensure_company_scope_for_write(
    user: Dict[str, Any],
    target_company_id: str,
    db: Database,
) -> str:
    role = str(user.get("role") or "").upper()
    if role not in {"HR", "ADMIN"}:
        raise HTTPException(status_code=403, detail="HR or Admin required")
    if role == "ADMIN":
        return target_company_id
    user_company_id = resolve_user_company_id(user, db)
    if user_company_id != str(target_company_id).strip():
        raise HTTPException(status_code=403, detail="Cannot modify another company's policy")
    return user_company_id


def ensure_company_scope_for_read(
    user: Dict[str, Any],
    target_company_id: str,
    db: Database,
) -> str:
    role = str(user.get("role") or "").upper()
    if role == "ADMIN":
        return target_company_id
    user_company_id = resolve_user_company_id(user, db)
    if user_company_id != str(target_company_id).strip():
        raise HTTPException(status_code=404, detail="Not found")
    return user_company_id


def resolve_target_company_id(
    user: Dict[str, Any],
    db: Database,
    explicit_company_id: Optional[str] = None,
) -> str:
    explicit = str(explicit_company_id or "").strip()
    role = str(user.get("role") or "").upper()
    if role == "ADMIN":
        if explicit:
            return explicit
        raise HTTPException(status_code=400, detail="company_id is required for admin policy mutations")
    company_id = resolve_user_company_id(user, db)
    if explicit and explicit != company_id:
        raise HTTPException(status_code=403, detail="Cannot target another company's policy")
    return company_id
