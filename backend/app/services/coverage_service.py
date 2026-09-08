"""
Admin coverage dashboard — live aggregation service.

Rolls the two acquisition tables up into ONE per-destination coverage payload:

  * FACTS     — ``requirement_items``, counted by ``review_status``
                (``approved`` = served, ``pending`` = awaiting review, ``rejected``).
  * PROVIDERS — ``supplier_service_capabilities``, counted by
                ``platform_vetting_status`` (``approved`` = live, ``pending``), with a
                per-service-category breakdown for the six serving categories.

The two tables key countries DIFFERENTLY: ``requirement_items.country_code`` holds
the catalog's FULL UPPERCASE NAME (``"IRELAND"``) while
``supplier_service_capabilities.country_code`` holds ISO-2 (``"IE"``). Both are
normalised to ISO-2 via ``requirements_country_key.to_iso_alpha2`` (the *broad*
resolver — ``to_iso`` is catalog-gated and would drop uncovered destinations) so a
destination's facts and providers land on the same row. See
``requirements_country_key.py`` for why the two keyings coexist.

Read-only. Nothing here writes, and nothing gates serving — ``review_status`` /
``platform_vetting_status`` are read straight through as counts. The result is
cached in-process (the Render service runs a single worker), so the admin page
loads the last snapshot instantly and forces a live recompute via ``?refresh=1``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text

from ..db import SessionLocal
from .registry_sources import CATEGORIES as SERVING_CATEGORIES
from .requirements_country_key import to_iso_alpha2

log = logging.getLogger(__name__)

_FACT_STATUSES = ("approved", "pending", "rejected")

# In-process cache (single worker on Render's free plan — see root CLAUDE.md).
# Recomputed on first call and whenever ``refresh=True`` is passed.
_CACHE: Optional[Dict[str, Any]] = None


def _iso_key(raw: Optional[str]) -> Optional[str]:
    """Canonical ISO-2 merge key.

    Falls back to the raw upper-cased value when unmappable so an unknown country
    still shows a row rather than vanishing — this view only *reports* counts, it
    never gates serving, so failing open is the correct behaviour here.
    """
    if not raw or not raw.strip():
        return None
    return to_iso_alpha2(raw) or raw.strip().upper()


def _display_name(catalog_name: Optional[str]) -> Optional[str]:
    """Title-case the catalog's UPPERCASE name for display (``"IRELAND"`` → ``"Ireland"``)."""
    if not catalog_name:
        return None
    return catalog_name.title() if catalog_name.isupper() else catalog_name


def _blank_row(iso: str) -> Dict[str, Any]:
    return {
        "iso": iso,
        "name": None,
        "catalog_name": None,
        "flag": None,
        "facts": {"approved": 0, "pending": 0, "rejected": 0, "total": 0},
        "providers": {
            "by_cat": {c: 0 for c in SERVING_CATEGORIES},
            "by_cat_detail": {},
            "approved": 0,
            "pending": 0,
            "total": 0,
        },
    }


def _compute() -> Dict[str, Any]:
    rows: Dict[str, Dict[str, Any]] = {}

    def row(iso: str) -> Dict[str, Any]:
        r = rows.get(iso)
        if r is None:
            r = _blank_row(iso)
            rows[iso] = r
        return r

    session = SessionLocal()
    try:
        fact_rows = session.execute(
            text(
                "SELECT country_code, review_status, count(*) AS n "
                "FROM requirement_items GROUP BY country_code, review_status"
            )
        ).all()
        cap_rows = session.execute(
            text(
                "SELECT country_code, service_category, platform_vetting_status, count(*) AS n "
                "FROM supplier_service_capabilities "
                "GROUP BY country_code, service_category, platform_vetting_status"
            )
        ).all()
        suppliers_total = session.execute(text("SELECT count(*) FROM suppliers")).scalar() or 0
        expert_verified = (
            session.execute(
                text(
                    "SELECT count(*) FROM requirement_items "
                    "WHERE verification_status = 'expert_verified'"
                )
            ).scalar()
            or 0
        )
        try:
            country_ref = session.execute(
                text("SELECT code, name, flag_emoji FROM countries")
            ).all()
        except Exception as exc:  # countries reference is optional / under-populated
            log.info("coverage: countries reference unavailable (%s)", exc)
            country_ref = []
    finally:
        session.close()

    for country_code, review_status, n in fact_rows:
        iso = _iso_key(country_code)
        if not iso:
            continue
        r = row(iso)
        if r["catalog_name"] is None:
            r["catalog_name"] = country_code
        st = (review_status or "").strip().lower()
        if st in _FACT_STATUSES:
            r["facts"][st] += n
        r["facts"]["total"] += n

    for country_code, service_category, vetting, n in cap_rows:
        iso = _iso_key(country_code)
        if not iso:
            continue
        p = row(iso)["providers"]
        p["total"] += n
        cat = (service_category or "").strip()
        st = (vetting or "").strip().lower()
        if cat:
            detail = p["by_cat_detail"].setdefault(
                cat, {"approved": 0, "pending": 0, "total": 0}
            )
            detail["total"] += n
            if st == "approved":
                detail["approved"] += n
            elif st == "pending":
                detail["pending"] += n
            if cat in p["by_cat"]:  # serving categories also keep a flat total
                p["by_cat"][cat] += n
        if st == "approved":
            p["approved"] += n
        elif st == "pending":
            p["pending"] += n

    ref = {(c or "").strip().upper(): (name, flag) for c, name, flag in country_ref if c}
    for iso, r in rows.items():
        name, flag = ref.get(iso, (None, None))
        r["name"] = name or _display_name(r["catalog_name"]) or iso
        r["flag"] = flag

    countries = sorted(rows.values(), key=lambda r: (r["name"] or r["iso"]).lower())
    extra_categories = sorted(
        {
            cat
            for r in countries
            for cat in r["providers"]["by_cat_detail"]
            if cat not in SERVING_CATEGORIES
        }
    )

    totals = {
        "destinations": len(countries),
        "facts_approved": sum(r["facts"]["approved"] for r in countries),
        "facts_pending": sum(r["facts"]["pending"] for r in countries),
        "facts_rejected": sum(r["facts"]["rejected"] for r in countries),
        "facts_total": sum(r["facts"]["total"] for r in countries),
        "caps_total": sum(r["providers"]["total"] for r in countries),
        "caps_approved": sum(r["providers"]["approved"] for r in countries),
        "caps_pending": sum(r["providers"]["pending"] for r in countries),
        "suppliers": int(suppliers_total),
        "expert_verified": int(expert_verified),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "serving_categories": list(SERVING_CATEGORIES),
        "extra_categories": extra_categories,
        "countries": countries,
        "totals": totals,
    }


def get_coverage_summary(*, refresh: bool = False) -> Dict[str, Any]:
    """Return the coverage snapshot, recomputing on the first call or when ``refresh``."""
    global _CACHE
    if refresh or _CACHE is None:
        _CACHE = _compute()
    return _CACHE
