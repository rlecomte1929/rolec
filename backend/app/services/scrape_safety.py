"""
Cost-control surface for the catalog scraper (Phase 2b-secured).

Layered protection — see docs/RECOMMENDATIONS_CATALOG_ROUTINE.md:
  L1: pre-check inside populate_destination_catalog (skip LLM when rows exist)
  L2: HR endpoint /api/hr/catalog/populate-with-ai goes through this module
  L3: per-company per-day quota — DEFAULT_DAILY_QUOTA distinct calls
  L4: destination allowlist — admin gates which (city, country) pairs scrape
  L7: audit row on every dispatch + every allowlist add

This module is purely the data layer. The HTTP endpoints in
backend/app/routers/hr_catalog.py + admin_catalog.py call into here.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ...database import db
from .audit_log_service import (
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
    insert_audit_log,
)

log = logging.getLogger(__name__)

DEFAULT_DAILY_QUOTA = 20


# ---------------------------------------------------------------------------
# Allowlist (L4)
# ---------------------------------------------------------------------------


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


def is_destination_allowlisted(city: str, country: Optional[str]) -> bool:
    city_n, country_n = _norm(city), _norm(country)
    if not city_n or not country_n:
        return False
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT 1 FROM catalog_destination_allowlist "
                "WHERE city = :city AND country = :country LIMIT 1"
            ),
            {"city": city_n, "country": country_n},
        ).first()
    return row is not None


def list_allowlist() -> List[Dict[str, Any]]:
    with db.engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT city, country, approved_by, approved_at, notes "
                "FROM catalog_destination_allowlist ORDER BY country, city"
            )
        ).mappings().all()
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        v = d.get("approved_at")
        if hasattr(v, "isoformat"):
            d["approved_at"] = v.isoformat()
        out.append(d)
    return out


def add_allowlist_entry(
    *,
    city: str,
    country: str,
    approved_by_user_id: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Admin-only. Idempotent."""
    city_n, country_n = _norm(city), _norm(country)
    if not city_n or not country_n:
        raise ValueError("city and country are both required")
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        existing = conn.execute(
            text(
                "SELECT city, country FROM catalog_destination_allowlist "
                "WHERE city = :city AND country = :country"
            ),
            {"city": city_n, "country": country_n},
        ).first()
        if not existing:
            conn.execute(
                text(
                    "INSERT INTO catalog_destination_allowlist "
                    "(city, country, approved_by, approved_at, notes) "
                    "VALUES (:city, :country, :actor, :now, :notes)"
                ),
                {
                    "city": city_n,
                    "country": country_n,
                    "actor": approved_by_user_id,
                    "now": now,
                    "notes": notes,
                },
            )
    _audit(
        entity_type="catalog_destination_allowlist",
        entity_id=f"{city_n}|{country_n}",
        action=ACTION_INSERT,
        actor_id=approved_by_user_id,
        new_value={"city": city_n, "country": country_n, "notes": notes},
    )
    return {"city": city_n, "country": country_n, "notes": notes}


# ---------------------------------------------------------------------------
# Quota (L3)
# ---------------------------------------------------------------------------


def _today_iso() -> str:
    return date.today().isoformat()


def get_quota_state(company_id: str) -> Dict[str, Any]:
    today = _today_iso()
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT calls_made FROM catalog_scrape_quota "
                "WHERE company_id = :co AND day = :day"
            ),
            {"co": company_id, "day": today},
        ).mappings().first()
    used = int(row["calls_made"]) if row else 0
    return {"day": today, "used": used, "limit": DEFAULT_DAILY_QUOTA, "remaining": max(0, DEFAULT_DAILY_QUOTA - used)}


def check_and_increment_quota(company_id: str) -> Dict[str, Any]:
    """
    Atomically check + increment the per-day counter. Returns the post-increment
    state plus an `allowed` flag. Caller bails when allowed=False.
    """
    today = _today_iso()
    with db.engine.begin() as conn:
        existing = conn.execute(
            text(
                "SELECT calls_made FROM catalog_scrape_quota "
                "WHERE company_id = :co AND day = :day"
            ),
            {"co": company_id, "day": today},
        ).mappings().first()
        used = int(existing["calls_made"]) if existing else 0
        if used >= DEFAULT_DAILY_QUOTA:
            return {"allowed": False, "day": today, "used": used, "limit": DEFAULT_DAILY_QUOTA, "remaining": 0}
        new_used = used + 1
        if existing:
            conn.execute(
                text(
                    "UPDATE catalog_scrape_quota SET calls_made = :n "
                    "WHERE company_id = :co AND day = :day"
                ),
                {"n": new_used, "co": company_id, "day": today},
            )
        else:
            conn.execute(
                text(
                    "INSERT INTO catalog_scrape_quota (company_id, day, calls_made) "
                    "VALUES (:co, :day, :n)"
                ),
                {"co": company_id, "day": today, "n": new_used},
            )
    return {
        "allowed": True,
        "day": today,
        "used": new_used,
        "limit": DEFAULT_DAILY_QUOTA,
        "remaining": DEFAULT_DAILY_QUOTA - new_used,
    }


# ---------------------------------------------------------------------------
# Ticket queue (L4 + L6)
# ---------------------------------------------------------------------------


def open_destination_request(
    *,
    city: str,
    country: str,
    category: str,
    requested_by_user_id: str,
    company_id: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    city_n, country_n = _norm(city), _norm(country)
    if not city_n or not country_n or not _norm(category):
        raise ValueError("city, country, and category are required")
    row_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        # Dedup: if there's already a pending request for the same triple, return that.
        existing = conn.execute(
            text(
                "SELECT * FROM catalog_destination_requests "
                "WHERE city = :city AND country = :country "
                "AND category = :cat AND status = 'pending' AND company_id = :co "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"city": city_n, "country": country_n, "cat": category, "co": company_id},
        ).mappings().first()
        if existing:
            return _ticket_to_dict(existing)
        conn.execute(
            text(
                "INSERT INTO catalog_destination_requests "
                "(id, city, country, category, requested_by, company_id, "
                " status, notes, created_at, updated_at) "
                "VALUES (:id, :city, :country, :cat, :req, :co, "
                " 'pending', :notes, :now, :now)"
            ),
            {
                "id": row_id, "city": city_n, "country": country_n, "cat": category,
                "req": requested_by_user_id, "co": company_id, "notes": notes,
                "now": now,
            },
        )
        new_row = conn.execute(
            text("SELECT * FROM catalog_destination_requests WHERE id = :id"),
            {"id": row_id},
        ).mappings().first()
    _audit(
        entity_type="catalog_destination_requests",
        entity_id=row_id,
        action=ACTION_INSERT,
        actor_id=requested_by_user_id,
        new_value={"city": city_n, "country": country_n, "category": category, "company_id": company_id},
    )
    return _ticket_to_dict(new_row)


def list_destination_requests(
    *,
    status: Optional[str] = None,
    company_id: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    where = []
    params: Dict[str, Any] = {"limit": int(max(1, min(limit, 500)))}
    if status:
        where.append("status = :status")
        params["status"] = status
    if company_id:
        where.append("company_id = :co")
        params["co"] = company_id
    sql = "SELECT * FROM catalog_destination_requests"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT :limit"
    with db.engine.begin() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [_ticket_to_dict(r) for r in rows]


def resolve_destination_request(
    *,
    request_id: str,
    new_status: str,
    actor_user_id: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    if new_status not in ("approved", "rejected"):
        raise ValueError("new_status must be 'approved' or 'rejected'")
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        existing = conn.execute(
            text("SELECT * FROM catalog_destination_requests WHERE id = :id"),
            {"id": request_id},
        ).mappings().first()
        if not existing:
            raise LookupError("Request not found")
        if existing["status"] != "pending":
            raise ValueError(f"Request already {existing['status']}")
        conn.execute(
            text(
                "UPDATE catalog_destination_requests "
                "SET status = :s, resolved_by = :actor, resolved_at = :now, "
                "    updated_at = :now, notes = COALESCE(:notes, notes) "
                "WHERE id = :id"
            ),
            {"s": new_status, "actor": actor_user_id, "now": now, "notes": notes, "id": request_id},
        )
        row = conn.execute(
            text("SELECT * FROM catalog_destination_requests WHERE id = :id"),
            {"id": request_id},
        ).mappings().first()
    _audit(
        entity_type="catalog_destination_requests",
        entity_id=request_id,
        action=ACTION_UPDATE,
        actor_id=actor_user_id,
        old_value={"status": existing["status"]},
        new_value={"status": new_status, "notes": notes},
    )
    return _ticket_to_dict(row)


def _ticket_to_dict(row: Any) -> Dict[str, Any]:
    d = dict(row)
    for k in ("created_at", "updated_at", "resolved_at"):
        v = d.get(k)
        if hasattr(v, "isoformat"):
            try:
                d[k] = v.isoformat()
            except Exception:
                d[k] = str(v)
    return d


# ---------------------------------------------------------------------------
# Audit helper — never raises
# ---------------------------------------------------------------------------


def _audit(
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_id: str,
    new_value: Optional[Dict[str, Any]] = None,
    old_value: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        with db.engine.begin() as conn:
            insert_audit_log(
                conn,
                entity_type=entity_type,
                entity_id=entity_id,
                action_type=action,
                old_value=old_value,
                new_value=new_value,
                actor_type=ACTOR_HUMAN,
                actor_id=actor_id,
            )
    except Exception:
        log.exception("audit_log write failed entity_type=%s entity_id=%s", entity_type, entity_id)
