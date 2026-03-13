"""
RFQ recipient mapping: resolve supplier_ids to vendor_ids for RFQ creation.
"""
from __future__ import annotations

from typing import List, Tuple

from ..db import SessionLocal
from .supplier_registry import get_supplier


def resolve_recipient_ids(ids: List[str]) -> Tuple[List[str], List[str]]:
    """
    Resolve recipient ids (supplier_ids) to vendor_ids.
    - If id is a supplier_id (in suppliers): use supplier.vendor_id or supplier_id as fallback
    - If not in suppliers: add to errors with clear message
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
                errors.append(f"Cannot create RFQ for item {item_id}: not a registered supplier")
                continue
            vendor_id = supplier.get("vendor_id") or supplier.get("id") or item_id
            vendor_id = str(vendor_id).strip()
            if vendor_id and vendor_id not in seen_vendors:
                seen_vendors.add(vendor_id)
                vendor_ids.append(vendor_id)

    return (vendor_ids, errors)
