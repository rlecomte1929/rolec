# backend/app/services/vendor_discovery/orchestrator.py
"""
Vendor discovery orchestrator (VEN-08) — reconciled to the Supplier Registry.

Chains: maps-provider fetch → accreditation enrich → quality rank → import into
`suppliers` as PENDING capabilities (the GAP 5 import path), so discovered vendors
flow through the admin vetting queue and never reach employees until approved.

Off by default: with DISCOVERY_PROVIDER unset the fetch returns [] and nothing is
written (zero cost). Idempotent: vendors whose name already exists are skipped.
(The VEN-08 spec's service_catalog_items staleness model is intentionally NOT used —
we unify on suppliers + the GAP 1-3 vetting lifecycle instead.)
"""
import logging
from typing import Any, Dict, List

from ...db import SessionLocal
from ...models import Supplier
from .. import maps_discovery, supplier_registry
from .accreditation_checker import enrich_with_accreditation
from .vendor_ranker import filter_and_rank_vendors

logger = logging.getLogger(__name__)


def discover_and_store_vendors(
    service_category: str,
    destination_city: str,
    destination_country: str,
    force_refresh: bool = False,  # reserved; name-dedup already makes this idempotent
) -> List[Dict[str, Any]]:
    """Full pipeline for one (category, city): fetch → enrich → rank → import to
    suppliers as pending. Returns the vendors imported this run."""
    candidates = maps_discovery.search_businesses(service_category, destination_city, destination_country)
    if not candidates:
        logger.info("No discovery results for %s/%s", service_category, destination_city)
        return []
    enrich_with_accreditation(candidates, service_category)
    top = filter_and_rank_vendors(candidates)
    if not top:
        logger.info("No vendors passed quality gate for %s/%s", service_category, destination_city)
        return []

    iso2 = (destination_country or "").strip().upper()[:2] or None
    imported: List[Dict[str, Any]] = []
    with SessionLocal() as session:
        existing = {(n or "").strip().lower() for (n,) in session.query(Supplier.name).all()}
        for v in top:
            name = (v.get("name") or "").strip()
            if not name or name.lower() in existing:
                continue
            cap: Dict[str, Any] = {
                "service_category": service_category,
                "city_name": destination_city,
                "specialization_tags": v.get("accreditation_tags") or [],
                "platform_vetting_status": "pending",
            }
            if iso2:
                cap["coverage_scope_type"] = "city"
                cap["country_code"] = iso2
            else:
                cap["coverage_scope_type"] = "global"
            source_url = (
                f"https://www.google.com/maps/place/?q=place_id:{v.get('place_id')}"
                if v.get("place_id") else v.get("website")
            )
            try:
                supplier_registry.create_supplier(session, {
                    "name": name,
                    "website": v.get("website"),
                    "contact_phone": v.get("phone"),
                    "status": "active",
                    "source": "scraper_discovery",
                    "source_url": source_url,
                    "capabilities": [cap],
                })
                existing.add(name.lower())
                imported.append(v)
            except ValueError:
                continue  # skip individual invalid rows, keep going
    logger.info("Imported %d discovered vendors for %s/%s (pending review)",
                len(imported), service_category, destination_city)
    return imported
