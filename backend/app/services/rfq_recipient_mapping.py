"""
RFQ recipient mapping: resolve what the employee shortlisted into a suppliers.id.

[AIQ-1520] This used to resolve supplier -> suppliers.vendor_id, because
rfq_recipients.vendor_id was assumed to reference vendors(id). That assumption is dead:

  * `vendors` is DEPRECATED for writes (20260825000000) and holds 8 rows against 90
    suppliers. `suppliers` is the source of truth (docs/supplier-systems-state.md).
  * Only 8 of 90 suppliers ever had a vendor_id, so RFQ creation hard-failed for the
    other 82 — including ALL 11 HR-approved movers.
  * rfq_recipients.vendor_id / quotes.vendor_id are now `text` and hold a suppliers.id
    (migration 20260918000000). The column keeps its old name until AIQ-1517 deletes the
    vendor portal and renames it.

WHAT AN ID CAN BE
-----------------
The employee shortlists a recommendation `item_id`, which is
service_catalog_items.external_id — a DIFFERENT id space from suppliers.id. The two used
to overlap by string coincidence; the AIQ-1511 dedupe removed that overlap. So we resolve
through the explicit link added in 20260918000000:

  1. already a suppliers.id            -> use it
  2. a service_catalog_items.external_id -> use that item's supplier_id
  3. anything else (e.g. an HR-custom vendor, which has no supplier row) -> honest error

external_id is globally unique, so no category is needed to disambiguate.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

from sqlalchemy import text

from ..db import SessionLocal
from .supplier_registry import get_supplier

log = logging.getLogger(__name__)


def _supplier_id_for_catalog_item(session, external_id: str):
    """Resolve a recommendation item_id (= service_catalog_items.external_id) to a
    suppliers.id via the explicit link. Returns (supplier_id, item_name) — supplier_id is
    None when the catalog item exists but has no supplier on record."""
    row = session.execute(
        text(
            "SELECT supplier_id, name FROM service_catalog_items "
            "WHERE external_id = :ext LIMIT 1"
        ),
        {"ext": external_id},
    ).mappings().first()
    if not row:
        return (None, None)
    sid = row.get("supplier_id")
    return (str(sid).strip() if sid else None, row.get("name"))


def resolve_recipient_ids(ids: List[str]) -> Tuple[List[str], List[str]]:
    """Resolve shortlisted recipient ids to suppliers.id.

    Returns (supplier_ids, errors). Order-preserving and deduped.

    The caller decides what to do with a partial result — an id we cannot resolve must be
    reported, never silently dropped, and must not poison the whole RFQ.
    """
    supplier_ids: List[str] = []
    errors: List[str] = []
    seen: set = set()

    with SessionLocal() as session:
        for raw in ids:
            if not raw or not str(raw).strip():
                continue
            item_id = str(raw).strip()

            # 1. Already a supplier.
            supplier = get_supplier(session, item_id)
            resolved = supplier.get("id") if supplier else None
            label = (supplier or {}).get("name") or item_id

            # 2. A catalog item — resolve through the explicit link.
            if not resolved:
                resolved, item_name = _supplier_id_for_catalog_item(session, item_id)
                if item_name:
                    label = item_name
                    if not resolved:
                        errors.append(
                            f"{item_name} cannot receive a quote request: no supplier on "
                            "record for it yet."
                        )
                        log.warning("rfq_recipient_mapping: catalog item %s has no supplier_id", item_id)
                        continue

            # 3. Neither.
            if not resolved:
                errors.append(
                    f"Cannot request a quote from {item_id}: it is not a supplier we can reach."
                )
                log.warning("rfq_recipient_mapping: %s resolves to no supplier", item_id)
                continue

            resolved = str(resolved).strip()
            if resolved not in seen:
                seen.add(resolved)
                supplier_ids.append(resolved)
            log.debug("rfq_recipient_mapping: %s -> supplier %s (%s)", item_id, resolved, label)

    return (supplier_ids, errors)
