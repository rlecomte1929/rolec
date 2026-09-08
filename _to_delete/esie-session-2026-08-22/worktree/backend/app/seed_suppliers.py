"""Seed Supplier Registry from recommendation datasets (movers, living_areas, schools)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from .db import SessionLocal
from .models import Supplier
from .services.supplier_registry import create_supplier

_CITY_TO_COUNTRY = {
    "Singapore": "SG", "Oslo": "NO", "Hong Kong": "HK", "Tokyo": "JP",
    "Asia-Pacific": "SG", "Asia": "SG", "Europe": "EU", "Global": None,
    "Australia": "AU", "NZ": "NZ", "New York": "US", "San Francisco": "US",
    # Cities missing here fall back to "US" (living_areas/schools blocks), which
    # mis-scoped Dubai rows to the US. Map the corridor destinations explicitly.
    "Dubai": "AE", "Munich": "DE",
}


def _ensure_supplier(session, item_id: str, name: str, data: dict) -> bool:
    """Create supplier with id=item_id if not exists. Returns True if created."""
    if session.query(Supplier).filter(Supplier.id == item_id).first():
        return False
    create_supplier(session, {"id": item_id, "name": name, "status": "active", "verified": False, **data})
    return True


def seed_suppliers_from_movers() -> int:
    """Seed suppliers from movers.json. Uses item_id so RFQ resolution works."""
    dataset_path = Path(__file__).resolve().parent / "recommendations" / "datasets" / "movers.json"
    if not dataset_path.exists():
        return 0

    with open(dataset_path, encoding="utf-8") as f:
        items = json.load(f)

    created = 0
    with SessionLocal() as session:
        for item in items:
            name = item.get("name")
            item_id = item.get("item_id")
            if not name or not item_id:
                continue
            service_areas = item.get("service_areas", [])
            city = service_areas[0] if service_areas else "Singapore"
            country = _CITY_TO_COUNTRY.get(city) or (city[:2].upper() if len(city) >= 2 else "SG")
            if _ensure_supplier(session, item_id, name, {
                "languages_supported": item.get("languages_supported", ["en"]),
                "capabilities": [{
                    "service_category": "movers",
                    "coverage_scope_type": "global" if "Global" in str(service_areas) else "country",
                    "country_code": country,
                    "specialization_tags": item.get("services_supported", []),
                    "corporate_clients": True,
                }],
                "scoring": {"average_rating": item.get("rating", 4.0), "review_count": item.get("rating_count", 0)},
            }):
                created += 1
        session.commit()
    return created


def seed_housing_agencies() -> int:
    """Seed housing AGENCIES (the gated, RFQ-backed housing suppliers) from
    housing_agencies.json.

    Distinct from the advisory neighbourhood overview (living_areas), which is NOT a
    supplier concept and is intentionally no longer seeded. Each agency is created as an
    **approved** supplier with a ``housing_agencies`` capability tagged with its sub-type
    (``serviced_apartment`` = temporary, ``rental_agency`` = permanent), plus a matching
    ``service_catalog_items`` master (external_id = supplier id). The catalog master lets
    apply_hr_curation resolve the agency AND lets the category-agnostic test-drive vendor
    seeding auto-select it, so agencies surface for provisioned companies without further
    wiring.
    """
    from .recommendations.plugins.housing_agencies import (
        TEMPORARY_TAG, PERMANENT_TAG, AREA_TAG_PREFIX,
    )

    path = Path(__file__).resolve().parent / "recommendations" / "datasets" / "housing_agencies.json"
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    _subtype_tag = {"temporary": TEMPORARY_TAG, "permanent": PERMANENT_TAG}
    now = datetime.utcnow().isoformat()
    created = 0
    with SessionLocal() as session:
        # One-time check: the coverage table may not exist yet (applied out-of-band).
        # Seed coverage only when present; the plugin falls back to area:* tags otherwise.
        try:
            session.execute(text("SELECT 1 FROM supplier_service_area_coverage LIMIT 1"))
            _has_coverage_table = True
        except Exception:
            session.rollback()
            _has_coverage_table = False
        for item in items:
            item_id = item.get("item_id")
            name = item.get("name")
            city = item.get("city", "Unknown")
            country = item.get("country") or _CITY_TO_COUNTRY.get(city) or "US"
            subtype = item.get("subtype", "permanent")
            if not item_id or not name:
                continue
            tag = _subtype_tag.get(subtype, PERMANENT_TAG)
            # Sub-type tag + neighbourhood-affinity tokens (area:<living_areas_id>) that
            # drive the Δ2 shortlist boost.
            area_tags = [f"{AREA_TAG_PREFIX}{a}" for a in (item.get("areas") or [])]
            if _ensure_supplier(session, item_id, name, {
                "capabilities": [{
                    "service_category": "housing_agencies",
                    "coverage_scope_type": "city",
                    "city_name": city,
                    "country_code": country,
                    "specialization_tags": [tag, *area_tags],
                    "corporate_clients": True,
                    # Agencies are pre-vetted representative suppliers → surface immediately.
                    "platform_vetting_status": "approved",
                }],
                "scoring": {"average_rating": item.get("rating", 4.5), "review_count": item.get("rating_count", 0)},
            }):
                created += 1
            # Idempotent catalog master (external_id = supplier id) so curation resolves
            # the agency and the test-drive CVS seeding can select it.
            exists = session.execute(
                text("SELECT 1 FROM service_catalog_items WHERE category = :cat AND external_id = :eid"),
                {"cat": "housing_agencies", "eid": item_id},
            ).first()
            if not exists:
                session.execute(
                    text(
                        "INSERT INTO service_catalog_items "
                        "(category, name, city, country, external_id, supplier_id, source, active, created_at, updated_at) "
                        "VALUES (:cat, :name, :city, :country, :eid, :sid, 'manual', true, :now, :now)"
                    ),
                    {"cat": "housing_agencies", "name": name, "city": city, "country": country,
                     "eid": item_id, "sid": item_id, "now": now},
                )
            # Real per-agency neighbourhood coverage — the curated source for the Δ2
            # shortlist boost. Idempotent (ON CONFLICT DO NOTHING).
            if _has_coverage_table:
                for area_id in (item.get("areas") or []):
                    session.execute(
                        text(
                            "INSERT INTO supplier_service_area_coverage "
                            "(supplier_id, service_category, area_id) "
                            "VALUES (:sid, 'housing_agencies', :area) "
                            "ON CONFLICT (supplier_id, service_category, area_id) DO NOTHING"
                        ),
                        {"sid": item_id, "area": area_id},
                    )
        session.commit()
    return created


def seed_suppliers_from_schools() -> int:
    """Seed suppliers from schools.json (item_id = s-*)."""
    path = Path(__file__).resolve().parent / "recommendations" / "datasets" / "schools.json"
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    created = 0
    with SessionLocal() as session:
        for item in items:
            item_id = item.get("item_id")
            name = item.get("name")
            city = item.get("city", "Unknown")
            if not item_id or not name:
                continue
            country = _CITY_TO_COUNTRY.get(city) or "US"
            if _ensure_supplier(session, item_id, name, {
                "capabilities": [{
                    "service_category": "schools",
                    "coverage_scope_type": "city",
                    "city_name": city,
                    "country_code": country,
                    "corporate_clients": True,
                }],
                "scoring": {"average_rating": item.get("rating", 4.0), "review_count": item.get("rating_count", 0)},
            }):
                created += 1
        session.commit()
    return created


def seed_suppliers_from_recommendation_datasets() -> int:
    """Seed schools, movers, and housing agencies so RFQ + curation work with real ids.

    living_areas is intentionally excluded: neighbourhoods are advisory content, not
    suppliers. Registering each `la-*` neighbourhood as a `living_areas` supplier minted
    field-poor shells that shadowed the real dataset rows and crashed the scorer (the
    Living Areas = 0 bug). Housing *agencies* (`seed_housing_agencies`) are the real,
    gated housing supplier concept that replaces that hack.
    """
    total = 0
    for fn in (seed_suppliers_from_schools, seed_suppliers_from_movers, seed_housing_agencies):
        try:
            total += fn()
        except Exception:
            pass
    return total
