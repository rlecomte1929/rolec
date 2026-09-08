"""Migrate the legacy `vendors` demo rows into the Supplier Registry (System A).

Usage:
    python -m backend.scripts.migrate_vendors_to_suppliers            # apply
    python -m backend.scripts.migrate_vendors_to_suppliers --dry-run  # preview

GAP 6 (lightweight convergence): prod's `vendors` table (redesign schema, ~8 demo
rows) is a second supplier surface used only by the legacy HR "Service providers"
list + the RFQ vendor-name join. `suppliers` + `supplier_service_capabilities` is
the real source of truth. This copies each active vendor into `suppliers`
(source='directory_import', vendor_id = the vendor's id) with ONE capability
mapped from the vendor's display category, marked platform_vetting_status='pending'
so it lands in the admin vetting queue rather than auto-surfacing to employees.

Idempotent: a vendor already migrated (a supplier row with that vendor_id) is
skipped. `vendors` is NOT modified or deleted (RFQ still reads it).
"""
from __future__ import annotations

import argparse
import logging
from typing import Any, Dict

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.db import SessionLocal
from backend.app.models import Supplier
from backend.app.services import supplier_registry

log = logging.getLogger(__name__)

# Vendor display `category` → ReloPass service_category slug.
CATEGORY_MAP: Dict[str, str] = {
    "Housing Search": "living_areas",
    "Moving & Freight": "movers",
    "Banking Setup": "banks",
    "Immigration Legal": "legal_admin",
    "School Search": "schools",
    "Tax Advisory": "tax_finance",
    "Destination Services": "general",
}


def _slug_for(category: str) -> str:
    return CATEGORY_MAP.get((category or "").strip(), "general")


def migrate(session: Session, *, dry_run: bool = False) -> Dict[str, Any]:
    """Copy active vendors into suppliers as pending. Returns {created, skipped}."""
    rows = session.execute(
        text(
            "SELECT id, name, category, website_url, email FROM vendors "
            "WHERE is_active = true ORDER BY name"
        )
    ).mappings().all()

    created = 0
    skipped = 0
    for v in rows:
        vendor_id = str(v["id"])
        already = (
            session.query(Supplier.id).filter(Supplier.vendor_id == vendor_id).first()
        )
        if already is not None:
            skipped += 1
            continue
        if dry_run:
            created += 1
            continue
        supplier_registry.create_supplier(session, {
            "name": v["name"],
            "website": v.get("website_url"),
            "contact_email": v.get("email"),
            "status": "active",
            "source": "directory_import",
            "source_reference": f"vendors:{vendor_id}",
            "vendor_id": vendor_id,
            "capabilities": [{
                "service_category": _slug_for(v.get("category")),
                "coverage_scope_type": "global",
                "platform_vetting_status": "pending",
            }],
        })
        created += 1
    return {"created": created, "skipped": skipped}


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Migrate vendors → suppliers (System A).")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing.")
    args = parser.parse_args(argv)
    with SessionLocal() as session:
        result = migrate(session, dry_run=args.dry_run)
    log.info(
        "%s: %d created, %d skipped (already migrated)",
        "DRY-RUN" if args.dry_run else "DONE", result["created"], result["skipped"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
