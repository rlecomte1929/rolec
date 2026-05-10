"""Seed Supplier Registry from recommendation datasets (movers, living_areas, schools)."""
from __future__ import annotations

import json
from pathlib import Path

from .db import SessionLocal
from .models import Supplier
from .services.supplier_registry import create_supplier

_CITY_TO_COUNTRY = {
    "Singapore": "SG", "Oslo": "NO", "Hong Kong": "HK", "Tokyo": "JP",
    "Asia-Pacific": "SG", "Asia": "SG", "Europe": "EU", "Global": None,
    "Australia": "AU", "NZ": "NZ", "New York": "US", "San Francisco": "US",
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


def seed_suppliers_from_living_areas() -> int:
    """Seed suppliers from living_areas.json (item_id = la-*)."""
    path = Path(__file__).resolve().parent / "recommendations" / "datasets" / "living_areas.json"
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
                    "service_category": "living_areas",
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
    """Seed living_areas, schools, movers so RFQ works with recommendation item_ids."""
    total = 0
    for fn in (seed_suppliers_from_living_areas, seed_suppliers_from_schools, seed_suppliers_from_movers):
        try:
            total += fn()
        except Exception:
            pass
    return total
