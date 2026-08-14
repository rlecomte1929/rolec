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
import unicodedata
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ...database import db

log = logging.getLogger(__name__)


def _canon_city(value: Optional[str]) -> str:
    """Canonicalise a city string for matching HR-curated rows to an employee's case.

    AIQ-1457: HR writes ``destination_city`` from the destination *picker* string
    (e.g. "Zürich") while the employee read passes the *intake-captured* case city
    (e.g. "Zurich") — separately-sourced strings that diverge by case, surrounding
    whitespace, or diacritics. A raw ``=`` comparison then returns zero rows and the
    employee wrongly sees "HR is finalizing providers." Normalise both sides to a
    lowercase, whitespace-trimmed, diacritic-stripped key so equivalent cities match.
    Cross-DB safe (pure Python — SQL ``LOWER`` does not strip diacritics on SQLite/PG).
    """
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(value))
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_marks.split()).lower()


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
    # [AIQ-1553] Coerce uuid columns to str, exactly as service_catalog._row_to_item does.
    # On Postgres, psycopg2 returns uuid columns as uuid.UUID objects; service_catalog
    # stringifies its master id, so the employee-recommendations filter compared
    # str(master["id"]) against a set of UUID objects — set membership always failed and
    # HR-approved masters were silently dropped to hr_pending (AIQ-1550 layer 3). SQLite
    # returns uuids as text, which is why the tests never caught it. Stringify here so all
    # consumers (and the master_item_id match) see consistent string ids.
    for k in ("id", "company_id", "master_item_id", "created_by_user_id"):
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


def list_curation(
    *,
    company_id: str,
    category: str,
    destination_city: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """All curation rows for the (company, category, city).

    AIQ-1457: the ``destination_city`` filter is applied in Python via ``_canon_city``
    rather than a raw SQL ``=`` so casing/whitespace/diacritic differences between HR's
    picker city and the employee's intake city don't hide curated vendors. City-scoped
    rows match when their canonical city equals the requested one; city-agnostic rows
    (``destination_city IS NULL``) always match.
    """
    sql = (
        "SELECT * FROM company_vendor_selections "
        "WHERE company_id = :co AND category = :cat "
        "ORDER BY display_order ASC, created_at ASC"
    )
    params: Dict[str, Any] = {"co": company_id, "cat": category}
    with db.engine.begin() as conn:
        rows = [_row_to_dict(r) for r in conn.execute(text(sql), params).mappings().all()]
    if destination_city is None:
        return rows
    want = _canon_city(destination_city)
    return [
        r
        for r in rows
        if not r.get("destination_city") or _canon_city(r.get("destination_city")) == want
    ]


class CountryMismatch(ValueError):
    """The selection's destination country disagrees with the catalog item's own country."""


def check_country_agreement(conn: Any, master_item_id: str, country: Optional[str]) -> Optional[str]:
    """Return a rejection reason, or None when the pair is acceptable.

    Audit finding F-2: HR curation rows were saved with a `country` that contradicts the
    `service_catalog_items` row they point at — 177 Norwegian companies approved a Sydney
    mover. Nothing at the write path ever compared the two.

    This is deliberately NOT a raise. Cross-country rows are still arriving daily (39 on
    2026-08-10, 102 on the 11th, 55 on the 12th), which is why the guard matters more than any
    one-off cleanup — but the only production writer, `hr_catalog.bulk_select`, loops toggles
    with no error handling, so raising would abort an HR user's entire save because of one bad
    row. The caller collects reasons and reports them instead.

    An UNKNOWN country is permitted. `service_catalog_items.country` is 981 of 985 populated;
    rejecting on absence would block legitimate saves for the remainder, and "we do not know"
    is not evidence of a mismatch.
    """
    if not master_item_id or not country:
        return None
    row = conn.execute(
        text("SELECT name, country FROM service_catalog_items WHERE id = :mid"),
        {"mid": master_item_id},
    ).mappings().first()
    if not row or not row.get("country"):
        return None
    item_country = str(row["country"]).strip().upper()
    want = str(country).strip().upper()
    if item_country == want:
        return None
    return (
        f"{row.get('name') or master_item_id} is in {item_country}; this selection is for "
        f"{want}. A vendor cannot serve a country it is not in."
    )


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
    """HR toggles a master item on/off for their company. Idempotent.

    Raises `CountryMismatch` when the destination country contradicts the catalog item's own
    country — see `check_country_agreement`. Callers handling batches should catch it per
    toggle so one bad row does not discard the rest.
    """
    now = datetime.utcnow().isoformat()
    # Bind a Python bool, not 1/0 — the `selected` column is a Postgres BOOLEAN and an
    # int bind raises psycopg2 DatatypeMismatch → 500 (SQLite coerces it, masking the bug).
    selected_bool = bool(selected)
    with db.engine.begin() as conn:
        # Before anything is written. A rejected toggle must leave no row behind.
        reason = check_country_agreement(conn, master_item_id, country)
        if reason:
            raise CountryMismatch(reason)
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
                {"sel": selected_bool, "country": country, "now": now, "id": existing["id"]},
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
                    "sel": selected_bool,
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
                ":id, :co, :cat, :city, :country, NULL, :payload, true, :order, "
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
