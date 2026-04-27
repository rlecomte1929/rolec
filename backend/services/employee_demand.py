"""
Employee demand signal — when an employee hits "HR is finalizing providers"
on the Recommendations page, we record an upsert in catalog_employee_demand
so HR can see who is waiting on what.

Strict best-effort: every insert path is wrapped, never raises. The
employee filter must keep working even if this table is gone.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..database import db

log = logging.getLogger(__name__)


def record_demand(
    *,
    company_id: str,
    category: str,
    destination_city: Optional[str],
    destination_country: Optional[str] = None,
    employee_user_id: Optional[str] = None,
) -> None:
    """Upsert a (company, category, city) row; bump count + last_seen_at."""
    if not company_id or not category:
        return
    now = datetime.utcnow().isoformat()
    try:
        with db.engine.begin() as conn:
            existing = conn.execute(
                text(
                    "SELECT id, demand_count FROM catalog_employee_demand "
                    "WHERE company_id = :co AND category = :cat "
                    "AND COALESCE(destination_city, '') = COALESCE(:city, '')"
                ),
                {"co": company_id, "cat": category, "city": destination_city},
            ).mappings().first()
            if existing:
                conn.execute(
                    text(
                        "UPDATE catalog_employee_demand SET "
                        "demand_count = demand_count + 1, "
                        "last_seen_at = :now, "
                        "last_seen_by_user_id = :uid, "
                        "destination_country = COALESCE(:country, destination_country) "
                        "WHERE id = :id"
                    ),
                    {"now": now, "uid": employee_user_id, "country": destination_country, "id": existing["id"]},
                )
            else:
                conn.execute(
                    text(
                        "INSERT INTO catalog_employee_demand ("
                        "id, company_id, category, destination_city, destination_country, "
                        "last_seen_by_user_id, last_seen_at, demand_count, created_at) "
                        "VALUES (:id, :co, :cat, :city, :country, :uid, :now, 1, :now)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "co": company_id, "cat": category,
                        "city": destination_city, "country": destination_country,
                        "uid": employee_user_id, "now": now,
                    },
                )
    except Exception:
        log.exception(
            "record_demand failed company=%s category=%s city=%s",
            company_id, category, destination_city,
        )


def list_demand_for_company(company_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    """HR-side read. Most recently-seen first."""
    if not company_id:
        return []
    with db.engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, company_id, category, destination_city, destination_country, "
                "last_seen_by_user_id, last_seen_at, demand_count "
                "FROM catalog_employee_demand "
                "WHERE company_id = :co "
                "ORDER BY last_seen_at DESC LIMIT :limit"
            ),
            {"co": company_id, "limit": int(max(1, min(limit, 500)))},
        ).mappings().all()
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        v = d.get("last_seen_at")
        if hasattr(v, "isoformat"):
            d["last_seen_at"] = v.isoformat()
        out.append(d)
    return out
