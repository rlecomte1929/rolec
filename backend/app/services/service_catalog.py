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

from sqlalchemy import bindparam, text

from ...database import db

log = logging.getLogger(__name__)

VALID_SOURCES = ("scraper", "manual", "seed", "hr_promoted", "registry_promoted")


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
    # id / created_by_user_id are uuid in Postgres → coerce to str so the
    # CatalogItemRead response_model (str) validates. SQLite returns them as text
    # already, which is why the SQLite tests never caught the prod 500.
    for k in ("id", "created_by_user_id"):
        if d.get(k) is not None:
            d[k] = str(d[k])
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
        where.append("active = true")
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
    supplier_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Insert a row, or update in place when (category, external_id) already
    exists. Used by the JSON→DB backfill (idempotent re-runs) and later
    by per-category scrapers (re-scraping shouldn't duplicate).

    AIQ-2095: pass ``supplier_id`` to LINK the master to a suppliers-registry
    row — the join the employee recommendation/curation paths use to reach a
    promoted supplier. When ``supplier_id`` is None the emitted SQL is
    byte-identical to before (the column is not referenced), so existing callers
    and their SQLite fixtures are unaffected.
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
            set_supplier = ", supplier_id = :supplier_id" if supplier_id is not None else ""
            params = {
                "city": city,
                "country": country,
                "name": name,
                "attr": attr_json,
                "source": source,
                "now": now,
                "id": existing["id"],
            }
            if supplier_id is not None:
                params["supplier_id"] = supplier_id
            conn.execute(
                text(
                    "UPDATE service_catalog_items SET "
                    "city = :city, country = :country, name = :name, "
                    "attributes_json = :attr, source = :source, "
                    "active = true, updated_at = :now" + set_supplier + " "
                    "WHERE id = :id"
                ),
                params,
            )
            row_id = existing["id"]
        else:
            row_id = str(uuid.uuid4())
            cols = (
                "id, category, city, country, name, attributes_json, "
                "source, active, external_id, created_at, updated_at, "
                "created_by_user_id"
            )
            vals = (
                ":id, :category, :city, :country, :name, :attr, "
                ":source, 1, :eid, :now, :now, :actor"
            )
            params = {
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
            }
            if supplier_id is not None:
                cols += ", supplier_id"
                vals += ", :supplier_id"
                params["supplier_id"] = supplier_id
            conn.execute(
                text(f"INSERT INTO service_catalog_items ({cols}) VALUES ({vals})"),
                params,
            )
        row = conn.execute(
            text("SELECT * FROM service_catalog_items WHERE id = :id"),
            {"id": row_id},
        ).mappings().first()
    return _row_to_item(row)


def merge_attributes(item_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Shallow-merge ``patch`` into a row's ``attributes_json``, preserving any
    keys not in the patch. Used by the service-type backfill to add
    ``service_types`` to existing rows without rewriting the rest of the blob.
    Returns the updated item, or None if the row doesn't exist."""
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        existing = conn.execute(
            text("SELECT attributes_json FROM service_catalog_items WHERE id = :id"),
            {"id": item_id},
        ).mappings().first()
        if not existing:
            return None
        cur = existing["attributes_json"]
        if isinstance(cur, str):
            try:
                cur = json.loads(cur)
            except (json.JSONDecodeError, TypeError):
                cur = {}
        if not isinstance(cur, dict):
            cur = {}
        cur.update(patch or {})
        conn.execute(
            text(
                "UPDATE service_catalog_items SET attributes_json = :attr, "
                "updated_at = :now WHERE id = :id"
            ),
            {"attr": json.dumps(cur, default=str), "now": now, "id": item_id},
        )
        row = conn.execute(
            text("SELECT * FROM service_catalog_items WHERE id = :id"),
            {"id": item_id},
        ).mappings().first()
    return _row_to_item(row)


def find_master_by_external_id(category: str, external_id: str) -> Optional[Dict[str, Any]]:
    """
    Resolve a master row by its (category, external_id) tuple. Used by the
    employee-recommendations filter to map plugin output (keyed by item_id,
    which is the JSON's external_id) back to the master row's UUID, so HR's
    selections-by-master_item_id can be applied.
    """
    if not external_id:
        return None
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT * FROM service_catalog_items "
                "WHERE category = :cat AND external_id = :eid AND active = true"
            ),
            {"cat": category, "eid": external_id},
        ).mappings().first()
    return _row_to_item(row) if row else None


def find_master_by_category_name(category: str, name: str) -> Optional[Dict[str, Any]]:
    """Resolve a master by (category, case-insensitive trimmed name) — the shape of the
    ``uq_service_catalog_items_category_name_ci`` UNIQUE index on
    ``(category, lower(trim(name)))``.

    [AIQ-2095] The registry-promotion link-or-insert path uses this: an approved supplier
    whose name already exists as a (usually crowdsourced, ``supplier_id``-less) catalog row
    must LINK that row rather than INSERT a duplicate the unique index would reject. Not
    filtered on ``active`` on purpose — the unique index covers inactive rows too, so an
    inactive twin must still be found (and can be re-linked/reactivated) instead of causing
    a silent insert failure."""
    nm = (name or "").strip()
    if not category or not nm:
        return None
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT * FROM service_catalog_items "
                "WHERE category = :cat AND lower(trim(name)) = lower(trim(:nm)) "
                "LIMIT 1"
            ),
            {"cat": category, "nm": nm},
        ).mappings().first()
    return _row_to_item(row) if row else None


def clear_master_country(item_id: str) -> None:
    """[AIQ-2195] Promote a linked master to country-agnostic (``country = NULL``).

    Coverage then comes from ``supplier_service_capabilities.country_code`` at
    serve time (ADR-002 Option B). Touches only ``country`` and ``updated_at``.
    """
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE service_catalog_items SET country = NULL, updated_at = :now "
                "WHERE id = :id"
            ),
            {"now": now, "id": item_id},
        )


def link_supplier_to_master(
    item_id: str, supplier_id: str, country: Optional[str] = None
) -> None:
    """[AIQ-2095] Attach a suppliers-registry id to an existing master, making that catalog
    row resolvable to the supplier by the recommendation/curation path. Reactivates the row
    and fills ``country`` only when it has none; never overwrites an existing ``supplier_id``
    (the caller checks that first)."""
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE service_catalog_items SET supplier_id = :sid, active = true, "
                "updated_at = :now, country = COALESCE(country, :country) WHERE id = :id"
            ),
            {"sid": supplier_id, "now": now, "country": country, "id": item_id},
        )


def find_master_by_supplier_or_external_id(
    category: str, item_id: str
) -> Optional[Dict[str, Any]]:
    """
    Resolve a master row for a recommendation item that may be keyed EITHER by the
    JSON dataset's ``external_id`` OR by a supplier-registry UUID.

    AIQ-1550/AIQ-1688: registry-backed items carry ``item_id = supplier.id`` (a UUID),
    but their master rows are frequently keyed ``external_id = 'm-1'`` (a legacy static
    dataset id) with ``supplier_id`` pointing at that same UUID. ``find_master_by_external_id``
    only matched ``external_id``, so those registry items resolved to no master and were
    dropped by HR curation — HR-approved movers rendered as an empty category even though
    the supplier, its capability, and HR's approval all existed. Matching on ``supplier_id``
    as well closes that gap. The approval gate in ``apply_hr_curation`` is unchanged: the
    resolved master must still be in HR's approved set to be shown.
    """
    if not item_id:
        return None
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT * FROM service_catalog_items "
                "WHERE category = :cat AND active = true "
                "  AND (external_id = :id OR CAST(supplier_id AS TEXT) = :id) "
                # external_id-keyed match wins when both a legacy static row and a
                # registry row exist, keeping behaviour stable for static datasets.
                "ORDER BY (external_id = :id) DESC "
                "LIMIT 1"
            ),
            {"cat": category, "id": str(item_id)},
        ).mappings().first()
    return _row_to_item(row) if row else None


def find_masters_by_supplier_or_external_ids(
    category: str, item_ids: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Batched ``find_master_by_supplier_or_external_id``: map each id in ``item_ids`` to
    its master row. Ids that resolve to nothing are simply absent from the result.

    AIQ-1700: curation now runs over the FULL ranked candidate list rather than the
    ``top_n`` slice, so resolving one id per query turned a ~10-query step into one
    query per candidate (up to ~80 for registry-heavy categories, multiplied by every
    category on the batch endpoint). Same matching rule as the single-id resolver,
    including the ``external_id``-wins tiebreak when a legacy static row and a registry
    row both answer to the same id.
    """
    ids = [str(i) for i in item_ids if i]
    if not ids:
        return {}
    stmt = text(
        "SELECT * FROM service_catalog_items "
        "WHERE category = :cat AND active = true "
        "  AND (external_id IN :ids OR CAST(supplier_id AS TEXT) IN :ids)"
    ).bindparams(bindparam("ids", expanding=True))
    with db.engine.begin() as conn:
        rows = conn.execute(stmt, {"cat": category, "ids": ids}).mappings().all()

    by_external: Dict[str, Any] = {}
    by_supplier: Dict[str, Any] = {}
    for row in rows:
        ext = row.get("external_id")
        sup = row.get("supplier_id")
        if ext is not None:
            by_external.setdefault(str(ext), row)
        if sup is not None:
            by_supplier.setdefault(str(sup), row)

    out: Dict[str, Dict[str, Any]] = {}
    for i in ids:
        # external_id first — mirrors the single-id resolver's ORDER BY tiebreak.
        row = by_external.get(i) or by_supplier.get(i)
        if row is not None:
            out[i] = _row_to_item(row)
    return out


def find_masters_by_ids(ids: List[str]) -> List[Dict[str, Any]]:
    """Active master rows for the given ``service_catalog_items.id`` values.

    AIQ-1857: the employee path needs to read an HR-approved master directly, rather
    than only reaching it via an engine candidate's external_id/supplier_id. Most
    catalog rows carry no ``supplier_id`` (measured 2026-08-17: 905 of 967 active
    rows, and 46 of 46 for Paris), so a vendor HR approved is otherwise unreachable
    for the employee no matter how it is scored.

    ``active = true`` still applies — a deactivated master must not resurface.
    """
    wanted = [str(i) for i in ids if i]
    if not wanted:
        return []
    stmt = text(
        "SELECT * FROM service_catalog_items "
        "WHERE active = true AND CAST(id AS TEXT) IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    with db.engine.begin() as conn:
        rows = conn.execute(stmt, {"ids": wanted}).mappings().all()
    return [_row_to_item(r) for r in rows]


def external_ids_for_supplier_ids(category: str, supplier_ids: List[str]) -> set:
    """
    Return the ``external_id``s of active masters in ``category`` whose ``supplier_id``
    is one of ``supplier_ids``.

    AIQ-1690: the recommendation dataset can hold two rows for one supplier — the
    registry candidate (``item_id`` = supplier id) and its legacy static-dataset twin
    (``item_id`` = the master's ``external_id``, e.g. ``'m-1'``). They never collide on
    item_id, so both used to be scored and could occupy two ``top_n`` slots. This is the
    batched form of the ``supplier_id`` link ``find_master_by_supplier_or_external_id``
    resolves one item at a time, letting the engine drop the twin before scoring.
    """
    ids = [str(s) for s in supplier_ids if s]
    if not ids:
        return set()
    stmt = text(
        "SELECT external_id FROM service_catalog_items "
        "WHERE category = :cat AND active = true "
        "  AND external_id IS NOT NULL "
        "  AND CAST(supplier_id AS TEXT) IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    with db.engine.begin() as conn:
        rows = conn.execute(stmt, {"cat": category, "ids": ids}).fetchall()
    return {str(r[0]) for r in rows if r[0]}


def count_by_category_city(category: str, city: Optional[str] = None) -> int:
    """Coverage count helper used by Phase 1's catalog_coverage."""
    sql = "SELECT COUNT(*) FROM service_catalog_items WHERE category = :cat AND active = true"
    params: Dict[str, Any] = {"cat": category}
    if city is not None:
        sql += " AND city = :city"
        params["city"] = city
    with db.engine.begin() as conn:
        return int(conn.execute(text(sql), params).scalar() or 0)
