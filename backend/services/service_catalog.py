"""
Master service-catalog data access (Phase 2a).

Thin layer over the `service_catalog_items` table. Read-only helpers
plus an idempotent insert used by the JSON→DB backfill script and
(later) the per-category scrapers.

Authority model — important:
- This is the ADMIN-owned master catalog. Reads here are by category
  + city/country.
- HR's per-company curation lives in a separate table (Phase 2d).
- Employees never query this module directly; they go through the
  employee recommendations pipeline which (Phase 2c+) will join
  through the HR curation table.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..database import db

log = logging.getLogger(__name__)

VALID_SOURCES = ("scraper", "manual", "seed", "hr_promoted")


def _row_to_item(row: Any) -> Dict[str, Any]:
    d = dict(row)
    raw_attr = d.get("attributes_json")
    if isinstance(raw_attr, str):
        try:
            d["attributes_json"] = json.loads(raw_attr)
        except (TypeError, ValueError):
            d["attributes_json"] = {}
    elif raw_attr is None:
        d["attributes_json"] = {}
    if isinstance(d.get("active"), int):
        d["active"] = bool(d["active"])
    for k in ("created_at", "updated_at"):
        v = d.get(k)
        if hasattr(v, "isoformat"):
            try:
                d[k] = v.isoformat()
            except Exception:
                d[k] = str(v)
    return d


def list_items(
    category: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    source: Optional[str] = None,
    active_only: bool = True,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """
    Filtered list of master catalog items. All filters are AND-combined.
    Returns most-recently-updated first to keep ops dashboards stable.
    """
    where = []
    params: Dict[str, Any] = {"limit": int(max(1, min(limit, 1000)))}
    if category:
        where.append("category = :category")
        params["category"] = category
    if city:
        where.append("city = :city")
        params["city"] = city
    if country:
        where.append("country = :country")
        params["country"] = country
    if source:
        if source not in VALID_SOURCES:
            raise ValueError(f"source must be one of {VALID_SOURCES}")
        where.append("source = :source")
        params["source"] = source
    if active_only:
        where.append("active = 1")
    sql = "SELECT * FROM service_catalog_items"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY updated_at DESC LIMIT :limit"
    with db.engine.begin() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [_row_to_item(r) for r in rows]


def upsert_item(
    *,
    category: str,
    name: str,
    attributes: Dict[str, Any],
    source: str = "manual",
    city: Optional[str] = None,
    country: Optional[str] = None,
    external_id: Optional[str] = None,
    created_by_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Insert a row, or update in place when (category, external_id) already
    exists. Used by the JSON→DB backfill (idempotent re-runs) and later
    by per-category scrapers (re-scraping shouldn't duplicate).
    """
    if source not in VALID_SOURCES:
        raise ValueError(f"source must be one of {VALID_SOURCES}")
    now = datetime.utcnow().isoformat()
    attr_json = json.dumps(attributes or {}, default=str)
    with db.engine.begin() as conn:
        existing = None
        if external_id:
            existing = conn.execute(
                text(
                    "SELECT id FROM service_catalog_items "
                    "WHERE category = :cat AND external_id = :eid"
                ),
                {"cat": category, "eid": external_id},
            ).mappings().first()
        if existing:
            conn.execute(
                text(
                    "UPDATE service_catalog_items SET "
                    "city = :city, country = :country, name = :name, "
                    "attributes_json = :attr, source = :source, "
                    "active = 1, updated_at = :now "
                    "WHERE id = :id"
                ),
                {
                    "city": city,
                    "country": country,
                    "name": name,
                    "attr": attr_json,
                    "source": source,
                    "now": now,
                    "id": existing["id"],
                },
            )
            row_id = existing["id"]
        else:
            row_id = str(uuid.uuid4())
            conn.execute(
                text(
                    "INSERT INTO service_catalog_items ("
                    "id, category, city, country, name, attributes_json, "
                    "source, active, external_id, created_at, updated_at, "
                    "created_by_user_id) VALUES ("
                    ":id, :category, :city, :country, :name, :attr, "
                    ":source, 1, :eid, :now, :now, :actor)"
                ),
                {
                    "id": row_id,
                    "category": category,
                    "city": city,
                    "country": country,
                    "name": name,
                    "attr": attr_json,
                    "source": source,
                    "eid": external_id,
                    "now": now,
                    "actor": created_by_user_id,
                },
            )
        row = conn.execute(
            text("SELECT * FROM service_catalog_items WHERE id = :id"),
            {"id": row_id},
        ).mappings().first()
    return _row_to_item(row)


def count_by_category_city(category: str, city: Optional[str] = None) -> int:
    """Coverage count helper used by Phase 1's catalog_coverage."""
    sql = "SELECT COUNT(*) FROM service_catalog_items WHERE category = :cat AND active = 1"
    params: Dict[str, Any] = {"cat": category}
    if city is not None:
        sql += " AND city = :city"
        params["city"] = city
    with db.engine.begin() as conn:
        return int(conn.execute(text(sql), params).scalar() or 0)
