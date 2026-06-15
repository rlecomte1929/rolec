"""Bridge service selections + quote requests into the live roadmap.

`case_milestones` is the roadmap the employee sees (via the relocation plan view).
This module manages ONLY rows with source='service' — it never touches AI,
deterministic-seed, or manual milestones.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from backend.app.services.service_roadmap_steps import (
    steps_for_service, service_key_for_category, _canonical_service_key,
)

log = logging.getLogger(__name__)

# Base sort_order offset per service so service clusters sit after the
# deterministic/AI milestones (which use small sort_orders).
_SERVICE_SORT_BASE = 1000


def _milestone_type(service_key: str, step_key: str) -> str:
    return f"service_{service_key}_{step_key}"


def reconcile_service_milestones(
    db: Any, case_id: str, selected_services: Sequence[str],
    *, request_id: Optional[str] = None,
) -> dict:
    """Make source='service' milestones match `selected_services`. Idempotent.

    Returns {"added": int, "removed": int, "kept": int}. Best-effort: callers
    should wrap so a failure never breaks the originating request.
    """
    # Canonicalise + drop unknown services (no steps in the library).
    keys = []
    for raw in selected_services or []:
        ck = _canonical_service_key(raw)
        if steps_for_service(ck):
            if ck not in keys:
                keys.append(ck)
        else:
            log.info("reconcile_service_milestones: skipping unknown service '%s'", raw)

    # Remove service rows for deselected services first.
    db.delete_service_milestones_not_in(case_id, keys, request_id=request_id)

    existing = {
        m["milestone_type"]: m
        for m in db.list_case_milestones(case_id, request_id=request_id)
        if m.get("source") == "service"
    }

    added = kept = 0
    for service_key in keys:
        for step in steps_for_service(service_key):
            mt = _milestone_type(service_key, step.key)
            row = existing.get(mt)
            if row:
                # Keep employee progress: only refresh copy, never reset status.
                db.upsert_case_milestone(
                    case_id, mt, step.title, description=step.description,
                    sort_order=_SERVICE_SORT_BASE + step.sort_offset,
                    status=row.get("status", "pending"),
                    source="service", service_key=service_key,
                    milestone_id=row["id"], request_id=request_id,
                )
                kept += 1
            else:
                db.upsert_case_milestone(
                    case_id, mt, step.title, description=step.description,
                    sort_order=_SERVICE_SORT_BASE + step.sort_offset,
                    status="pending", source="service", service_key=service_key,
                    request_id=request_id,
                )
                added += 1

    removed_total = len(existing) - kept
    return {"added": added, "removed": max(removed_total, 0), "kept": kept}


def advance_quote_step(
    db: Any, case_id: str, service_categories: Sequence[str],
    *, quote_request_id: str, request_id: Optional[str] = None,
) -> int:
    """Flip each requested service's '*_quote' step to in_progress and stamp the
    quote_request_id in notes. Returns the number of steps advanced. No-op for
    categories that don't resolve or have no quote step. Best-effort."""
    targets = set()
    for cat in service_categories or []:
        key = service_key_for_category(cat)
        if not key:
            continue
        for step in steps_for_service(key):
            if step.key.endswith("quote"):
                targets.add(_milestone_type(key, step.key))

    if not targets:
        return 0

    advanced = 0
    rows = {
        m["milestone_type"]: m
        for m in db.list_case_milestones(case_id, request_id=request_id)
        if m.get("source") == "service"
    }
    for mt in targets:
        row = rows.get(mt)
        if not row:
            continue
        db.upsert_case_milestone(
            case_id, mt, row["title"],
            status="in_progress", source="service",
            service_key=row.get("service_key"),
            notes=f"quote_request_id={quote_request_id}",
            milestone_id=row["id"], request_id=request_id,
        )
        advanced += 1
    return advanced
