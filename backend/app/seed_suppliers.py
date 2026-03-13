"""Seed Supplier Registry from recommendation datasets (movers, etc.)."""
from __future__ import annotations

import json
from pathlib import Path

from .db import SessionLocal
from .models import Supplier
from .services.supplier_registry import create_supplier


def seed_suppliers_from_movers() -> int:
    """Seed suppliers from movers.json. Returns count created."""
    dataset_path = Path(__file__).resolve().parent / "recommendations" / "datasets" / "movers.json"
    if not dataset_path.exists():
        return 0

    with open(dataset_path, encoding="utf-8") as f:
        items = json.load(f)

    created = 0
    with SessionLocal() as session:
        for item in items:
            name = item.get("name")
            if not name:
                continue
            # Check if already exists
            existing = session.query(Supplier).filter(Supplier.name == name).first()
            if existing:
                continue

            service_areas = item.get("service_areas", [])
            _city_to_country = {"Singapore": "SG", "Oslo": "NO", "Hong Kong": "HK", "Tokyo": "JP", "Asia-Pacific": "SG", "Asia": "SG", "Europe": "EU", "Global": None, "Australia": "AU", "NZ": "NZ"}
            country = None
            for area in service_areas:
                country = _city_to_country.get(area) or (area[:2].upper() if len(area) >= 2 else None)
                if country:
                    break
            country = country or "SG"

            create_supplier(session, {
                "name": name,
                "status": "active",
                "languages_supported": item.get("languages_supported", ["en"]),
                "verified": False,
                "capabilities": [{
                    "service_category": "movers",
                    "coverage_scope_type": "global" if "Global" in str(service_areas) else "country",
                    "country_code": country,
                    "specialization_tags": item.get("services_supported", []),
                    "corporate_clients": True,
                }],
                "scoring": {
                    "average_rating": item.get("rating", 4.0),
                    "review_count": item.get("rating_count", 0),
                },
            })
            created += 1
        session.commit()
    return created
