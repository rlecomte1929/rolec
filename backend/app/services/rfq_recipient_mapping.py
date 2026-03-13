"""
RFQ recipient mapping: resolve supplier_ids to vendor_ids for RFQ creation.

For Supabase/Postgres: rfq_recipients.vendor_id must reference vendors(id).
Suppliers must have vendor_id set to a valid vendors row; otherwise RFQ creation fails.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

from ..db import SessionLocal
from .supplier_registry import get_supplier

log = logging.getLogger(__name__)


def resolve_recipient_ids(ids: List[str]) -> Tuple[List[str], List[str]]:
    """
    Resolve recipient ids (supplier_ids) to vendor_ids.

    - If id is a supplier_id (in suppliers): use supplier.vendor_id only.
    - vendor_id is REQUIRED: supplier.id is NOT used as fallback, since vendors
      table is separate and rfq_recipients.vendor_id must reference vendors(id).
    - If supplier has no vendor_id: add to errors with clear message.
    - If not in suppliers: add to errors with clear message.

    Returns (vendor_ids, errors).
    """
    vendor_ids: List[str] = []
    errors: List[str] = []
    seen_vendors: set = set()

    with SessionLocal() as session:
        for item_id in ids:
            if not item_id or not str(item_id).strip():
                continue
            item_id = str(item_id).strip()
            supplier = get_supplier(session, item_id)
            if not supplier:
                err = f"Cannot create RFQ for {item_id}: not a registered supplier"
                errors.append(err)
                log.warning("rfq_recipient_mapping: %s", err)
                continue

            vendor_id_raw = supplier.get("vendor_id")
            if not vendor_id_raw or not str(vendor_id_raw).strip():
                err = (
                    f"Supplier {item_id} ({supplier.get('name', item_id)}) has no vendor_id. "
                    "Add vendor_id in Admin > Suppliers before using for RFQ."
                )
                errors.append(err)
                log.warning("rfq_recipient_mapping: %s", err)
                continue

            vendor_id = str(vendor_id_raw).strip()
            if vendor_id not in seen_vendors:
                seen_vendors.add(vendor_id)
                vendor_ids.append(vendor_id)

    return (vendor_ids, errors)
