# backend/app/tasks/vendor_freshness_refresh.py
"""
Vendor freshness refresh job (VEN-11) — reconciled to the Supplier Registry.

Re-fetches discovery-sourced suppliers (source='scraper_discovery') from Google
Places by their place_id, refreshes their rating/review_count, and SUSPENDS the
capabilities of any vendor that is now CLOSED_PERMANENTLY so it drops out of
recommendations (GAP 3 filters on 'approved'). Marks each refreshed supplier's
scoring last_verified_at so it isn't re-checked until it's stale again.

Run manually: python3 -m backend.app.tasks.vendor_freshness_refresh [--dry-run]
No-op when the discovery provider isn't configured (refresh returns None → error
counted, no cost). Off by default.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Optional

from ..config.vendor_discovery import VENDOR_QUALITY_THRESHOLDS
from ..db import SessionLocal
from ..models import Supplier, SupplierScoringMetadata, SupplierServiceCapability
from ..services.maps_discovery import refresh_vendor_by_place_id

logger = logging.getLogger(__name__)

_PLACE_ID_RE = re.compile(r"place_id:([^&\s]+)")


def _place_id_from(source_url: Optional[str]) -> Optional[str]:
    if not source_url:
        return None
    m = _PLACE_ID_RE.search(source_url)
    return m.group(1) if m else None


def refresh_stale_vendors(dry_run: bool = False) -> Dict[str, int]:
    """Refresh discovery-sourced suppliers stale beyond freshness_days.
    Returns {checked, updated, closed, errors}."""
    stats = {"checked": 0, "updated": 0, "closed": 0, "errors": 0}
    days = VENDOR_QUALITY_THRESHOLDS.get("freshness_days", 90)
    cutoff = datetime.utcnow() - timedelta(days=days)

    with SessionLocal() as session:
        rows = (
            session.query(Supplier, SupplierScoringMetadata)
            .outerjoin(SupplierScoringMetadata, SupplierScoringMetadata.supplier_id == Supplier.id)
            .filter(Supplier.source == "scraper_discovery")
            .filter(Supplier.source_url.isnot(None))
            .limit(500)
            .all()
        )
        for supplier, meta in rows:
            place_id = _place_id_from(supplier.source_url)
            if not place_id:
                continue
            last_verified = meta.last_verified_at if meta else None
            if last_verified is not None and last_verified > cutoff:
                continue  # still fresh — skip
            stats["checked"] += 1
            if dry_run:
                logger.info("[dry-run] would refresh %s (%s)", supplier.name, place_id)
                continue

            fresh = refresh_vendor_by_place_id(place_id)
            if not fresh:
                stats["errors"] += 1
                continue

            if meta is None:
                meta = SupplierScoringMetadata(
                    supplier_id=supplier.id, review_count=0,
                    preferred_partner=False, premium_partner=False,
                )
                session.add(meta)
            if fresh.get("rating") is not None:
                meta.average_rating = fresh["rating"]
            if fresh.get("user_ratings_total") is not None:
                meta.review_count = fresh["user_ratings_total"]
            meta.last_verified_at = datetime.utcnow()

            if fresh.get("business_status") == "CLOSED_PERMANENTLY":
                session.query(SupplierServiceCapability).filter(
                    SupplierServiceCapability.supplier_id == supplier.id
                ).update({"platform_vetting_status": "suspended"})
                logger.warning("Vendor permanently closed — suspended: %s", supplier.name)
                stats["closed"] += 1
            else:
                stats["updated"] += 1

        if not dry_run:
            session.commit()
    logger.info("Vendor freshness refresh complete: %s", stats)
    return stats


def main(argv=None) -> int:
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Refresh stale discovery-sourced suppliers.")
    parser.add_argument("--dry-run", action="store_true", help="List stale vendors without fetching or writing.")
    args = parser.parse_args(argv)
    print(refresh_stale_vendors(dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
