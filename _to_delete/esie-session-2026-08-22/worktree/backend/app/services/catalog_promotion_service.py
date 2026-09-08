"""
[CATALOG-2] Promote popular HR custom vendors into the shared master catalog.

HR teams add custom vendors per (category, destination) into
``company_vendor_selections.custom_item_json`` (company-scoped). When the same
vendor is independently added by ``>= threshold`` distinct companies for the
same (category, city), that is a strong demand signal — promote a single
deduped record into ``service_catalog_items`` with ``source='hr_promoted'`` so
every company gets it for that destination.

No schema change: the ``hr_promoted`` source value already exists. The
promotion is idempotent — re-running does not create duplicates (a
deterministic ``external_id`` plus an existing-catalog guard), and one-off
custom vendors below the threshold are never promoted.

Grouping is done in Python rather than with Postgres ``jsonb`` operators so the
logic is portable and unit-testable against SQLite.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from ...database import db
from . import service_catalog

logger = logging.getLogger(__name__)

# Distinct-company count at/above which a custom vendor is promoted. Overridable
# via env so ops can tune it without a deploy; the API also accepts a per-call
# threshold.
DEFAULT_THRESHOLD = int(os.getenv("CATALOG_HR_PROMOTE_THRESHOLD", "2") or "2")


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _coerce_json(val: Any) -> Dict[str, Any]:
    """custom_item_json comes back as a dict (Postgres jsonb) or a string
    (SQLite text). Normalise to a dict; tolerate malformed values."""
    if isinstance(val, dict):
        return val
    if isinstance(val, (str, bytes)):
        try:
            out = json.loads(val)
            return out if isinstance(out, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def _summary(g: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category": g["category"],
        "city": g["city"],
        "country": g["country"],
        "name": g["name"],
    }


def promote_hr_vendors(
    *,
    threshold: Optional[int] = None,
    dry_run: bool = False,
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Detect and promote popular HR custom vendors.

    Returns a summary: ``{threshold, dry_run, groups_considered, promoted[],
    skipped_existing[], below_threshold}``.
    """
    thr = int(threshold) if threshold is not None else DEFAULT_THRESHOLD
    if thr < 1:
        raise ValueError("threshold must be >= 1")

    # 1) Load every HR custom-vendor addition (company-scoped).
    with db.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT company_id, category, destination_city, country, "
                "custom_item_json FROM company_vendor_selections "
                "WHERE custom_item_json IS NOT NULL"
            )
        ).mappings().all()

    # 2) Group by (category, normalized city, normalized name); count DISTINCT
    #    companies. The first non-empty value seen wins for the display fields.
    groups: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for r in rows:
        payload = _coerce_json(r["custom_item_json"])
        name = (payload.get("name") or "").strip()
        if not name:
            continue
        key = (_norm(r["category"]), _norm(r["destination_city"]), _norm(name))
        g = groups.setdefault(
            key,
            {
                "category": r["category"],
                "city": r["destination_city"],
                "country": r["country"],
                "name": name,
                "attributes": {k: v for k, v in payload.items() if k != "name"},
                "companies": set(),
            },
        )
        g["companies"].add(str(r["company_id"]))

    promoted: List[Dict[str, Any]] = []
    skipped_existing: List[Dict[str, Any]] = []
    below_threshold = 0

    for (cat_key, city_key, name_key), g in groups.items():
        n = len(g["companies"])
        if n < thr:
            below_threshold += 1
            continue

        # 3) Skip if this vendor already exists in the master for that
        #    (category, city) — don't duplicate seeded/scraped/manual rows.
        with db.engine.connect() as conn:
            existing = conn.execute(
                text(
                    "SELECT id FROM service_catalog_items "
                    "WHERE lower(category) = :cat "
                    "AND lower(coalesce(city, '')) = :city "
                    "AND lower(name) = :name LIMIT 1"
                ),
                {"cat": cat_key, "city": city_key, "name": name_key},
            ).first()
        if existing:
            skipped_existing.append({**_summary(g), "companies": n})
            continue

        if dry_run:
            promoted.append({**_summary(g), "companies": n, "dry_run": True})
            continue

        # 4) Promote a single deduped row. The deterministic external_id makes
        #    re-runs idempotent (upsert updates in place on (category, eid)).
        external_id = f"hr_promoted:{cat_key}:{city_key}:{name_key}"
        item = service_catalog.upsert_item(
            category=g["category"],
            name=g["name"],
            attributes=g["attributes"],
            source="hr_promoted",
            city=g["city"],
            country=g["country"],
            external_id=external_id,
            created_by_user_id=actor_id,
        )
        promoted.append({**_summary(g), "companies": n, "catalog_item_id": item.get("id")})

    logger.info(
        "catalog promotion: threshold=%s dry_run=%s promoted=%s skipped_existing=%s below_threshold=%s",
        thr, dry_run, len(promoted), len(skipped_existing), below_threshold,
    )
    return {
        "threshold": thr,
        "dry_run": dry_run,
        "groups_considered": len(groups),
        "promoted": promoted,
        "skipped_existing": skipped_existing,
        "below_threshold": below_threshold,
    }
