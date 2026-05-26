"""
HR per-company vendor curation (Phase 2d).

Middle tier of the authority chain:
  ADMIN owns service_catalog_items (Phase 2a).
  HR picks rows here per (company, category, destination).
  Employee API (Phase 2c+) joins through this table.

Two row shapes:
  - Master selection: master_item_id set, custom_item_json null
    → HR has decided about an admin master row (selected on/off)
  - Custom HR vendor: master_item_id null, custom_item_json set
    → HR added a vendor that's not in the master list
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ...database import db

log = logging.getLogger(__name__)


def _row_to_dict(row: Any) -> Dict[str, Any]:
    d = dict(row)
    raw = d.get("custom_item_json")
    if isinstance(raw, str):
        try:
            d["custom_item_json"] = json.loads(raw)
        except (TypeError, ValueError):
            d["custom_item_json"] = None
    if isinstance(d.get("selected"), int):
        d["selected"] = bool(d["selected"])
    for k in ("created_at", "updated_at"):
        v = d.get(k)
        if hasattr(v, "isoformat"):
            try:
                d[k] = v.isoformat()
            except Exception:
                d[k] = str(v)
    return d


def list_curation(
    *,
    company_id: str,
    category: str,
    destination_city: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """All curation rows for the (company, category, city)."""
    sql = (
        "SELECT * FROM company_vendor_selections "
        "WHERE company_id = :co AND category = :cat"
    )
    params: Dict[str, Any] = {"co": company_id, "cat": category}
    if destination_city is not None:
        sql += " AND (destination_city = :city OR destination_city IS NULL)"
        params["city"] = destination_city
    sql += " ORDER BY display_order ASC, created_at ASC"
    with db.engine.begin() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [_row_to_dict(r) for r in rows]


def upsert_master_selection(
    *,
    company_id: str,
    category: str,
    master_item_id: str,
    selected: bool,
    destination_city: Optional[str] = None,
    country: Optional[str] = None,
    actor_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """HR toggles a master item on/off for their company. Idempotent."""
    now = datetime.utcnow().isoformat()
    selected_int = 1 if selected else 0
    with db.engine.begin() as conn:
        existing = conn.execute(
            text(
                "SELECT id FROM company_vendor_selections "
                "WHERE company_id = :co AND category = :cat "
                "AND master_item_id = :mid "
                "AND COALESCE(destination_city, '') = COALESCE(:city, '')"
            ),
            {"co": company_id, "cat": category, "mid": master_item_id, "city": destination_city},
        ).mappings().first()
        if existing:
            conn.execute(
                text(
                    "UPDATE company_vendor_selections "
                    "SET selected = :sel, country = :country, updated_at = :now "
                    "WHERE id = :id"
                ),
                {"sel": selected_int, "country": country, "now": now, "id": existing["id"]},
            )
            row_id = existing["id"]
        else:
            row_id = str(uuid.uuid4())
            conn.execute(
                text(
                    "INSERT INTO company_vendor_selections ("
                    "id, company_id, category, destination_city, country, "
                    "master_item_id, custom_item_json, selected, display_order, "
                    "created_at, updated_at, created_by_user_id) VALUES ("
                    ":id, :co, :cat, :city, :country, :mid, NULL, :sel, 0, "
                    ":now, :now, :actor)"
                ),
                {
                    "id": row_id,
                    "co": company_id,
                    "cat": category,
                    "city": destination_city,
                    "country": country,
                    "mid": master_item_id,
                    "sel": selected_int,
                    "now": now,
                    "actor": actor_user_id,
                },
            )
        row = conn.execute(
            text("SELECT * FROM company_vendor_selections WHERE id = :id"),
            {"id": row_id},
        ).mappings().first()
    return _row_to_dict(row)


def add_custom_vendor(
    *,
    company_id: str,
    category: str,
    name: str,
    attributes: Dict[str, Any],
    destination_city: Optional[str] = None,
    country: Optional[str] = None,
    display_order: int = 0,
    actor_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """HR adds their own vendor that isn't in the admin master."""
    if not name or not name.strip():
        raise ValueError("name is required")
    payload = {"name": name.strip(), **{k: v for k, v in (attributes or {}).items() if k != "name"}}
    now = datetime.utcnow().isoformat()
    row_id = str(uuid.uuid4())
    with db.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO company_vendor_selections ("
                "id, company_id, category, destination_city, country, "
                "master_item_id, custom_item_json, selected, display_order, "
                "created_at, updated_at, created_by_user_id) VALUES ("
                ":id, :co, :cat, :city, :country, NULL, :payload, 1, :order, "
                ":now, :now, :actor)"
            ),
            {
                "id": row_id,
                "co": company_id,
                "cat": category,
                "city": destination_city,
                "country": country,
                "payload": json.dumps(payload, default=str),
                "order": display_order,
                "now": now,
                "actor": actor_user_id,
            },
        )
        row = conn.execute(
            text("SELECT * FROM company_vendor_selections WHERE id = :id"),
            {"id": row_id},
        ).mappings().first()
    return _row_to_dict(row)


def delete_custom_vendor(*, company_id: str, row_id: str) -> bool:
    """Tenant-scoped delete; only custom rows can be deleted (master ones get toggled off)."""
    with db.engine.begin() as conn:
        existing = conn.execute(
            text(
                "SELECT id, master_item_id FROM company_vendor_selections "
                "WHERE id = :id AND company_id = :co"
            ),
            {"id": row_id, "co": company_id},
        ).mappings().first()
        if not existing:
            return False
        if existing["master_item_id"] is not None:
            raise ValueError(
                "Cannot delete a master selection — toggle 'selected' to false instead."
            )
        conn.execute(
            text("DELETE FROM company_vendor_selections WHERE id = :id"),
            {"id": row_id},
        )
    return True
