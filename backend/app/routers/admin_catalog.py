"""
Admin endpoints for the master service catalog (Phase 2a).

Read-only here; Phase 2c adds the scraper-driven write endpoint and
Phase 2h adds the per-row promote/demote/remove admin UI surface.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth_deps import require_admin
from ...services import service_catalog

router = APIRouter(prefix="/api/admin/catalog", tags=["admin_catalog"])
logger = logging.getLogger(__name__)


class CatalogItemRead(BaseModel):
    id: str
    category: str
    city: Optional[str]
    country: Optional[str]
    name: str
    attributes_json: Dict[str, Any]
    source: str
    active: bool
    external_id: Optional[str]
    created_at: str
    updated_at: str
    created_by_user_id: Optional[str]


@router.get("/items", response_model=List[CatalogItemRead])
def list_catalog_items(
    category: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    source: Optional[str] = Query(None, description="One of: scraper, manual, seed, hr_promoted"),
    active_only: bool = Query(True),
    limit: int = Query(200, ge=1, le=1000),
    user: Dict[str, Any] = Depends(require_admin),
) -> List[Dict[str, Any]]:
    try:
        return service_catalog.list_items(
            category=category,
            city=city,
            country=country,
            source=source,
            active_only=active_only,
            limit=limit,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


# ---------------------------------------------------------------------------
# Phase 2b-secured: destination allowlist + ticket-queue admin
# ---------------------------------------------------------------------------


class AllowlistAddBody(BaseModel):
    city: str
    country: str
    notes: Optional[str] = None


class ResolveTicketBody(BaseModel):
    status: str  # "approved" | "rejected"
    notes: Optional[str] = None


@router.get("/destinations/allowlist")
def list_destination_allowlist(
    user: Dict[str, Any] = Depends(require_admin),
) -> List[Dict[str, Any]]:
    from ...services import scrape_safety
    return scrape_safety.list_allowlist()


@router.post("/destinations/allowlist")
def add_destination_to_allowlist(
    body: AllowlistAddBody,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    from ...services import scrape_safety
    try:
        return scrape_safety.add_allowlist_entry(
            city=body.city,
            country=body.country,
            approved_by_user_id=user["id"],
            notes=body.notes,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.get("/destination-requests")
def list_destination_requests(
    status: Optional[str] = None,
    user: Dict[str, Any] = Depends(require_admin),
) -> List[Dict[str, Any]]:
    """Admin queue of HR-opened tickets. ?status=pending|approved|rejected."""
    from ...services import scrape_safety
    if status and status not in ("pending", "approved", "rejected"):
        raise HTTPException(status_code=400, detail="status must be pending, approved, or rejected")
    return scrape_safety.list_destination_requests(status=status, limit=200)


@router.patch("/destination-requests/{request_id}")
def resolve_destination_request(
    request_id: str,
    body: ResolveTicketBody,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Admin approves or rejects a ticket. On 'approved', the (city, country)
    is added to the allowlist; the original requester can then re-trigger
    the populate-with-ai endpoint and the scrape will fire (subject to quota).
    """
    from ...services import scrape_safety
    try:
        ticket = scrape_safety.resolve_destination_request(
            request_id=request_id,
            new_status=body.status,
            actor_user_id=user["id"],
            notes=body.notes,
        )
    except LookupError as ex:
        raise HTTPException(status_code=404, detail=str(ex))
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))

    if ticket["status"] == "approved":
        try:
            scrape_safety.add_allowlist_entry(
                city=ticket["city"],
                country=ticket["country"],
                approved_by_user_id=user["id"],
                notes=f"Approved via ticket {request_id}",
            )
        except ValueError:
            pass
    return ticket


@router.get("/notification-counts")
def admin_notification_counts(
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Lightweight summary admin uses for nav badges:
      - pending_tickets: HR-opened destination requests waiting on admin
      - allowlisted_destinations: total approved destinations

    Computed via COUNT aggregates in a single connection. The earlier version
    fetched up to 500 row payloads from each table just to take len() — wasteful
    on the SQLAlchemy pool when polled every minute by the admin shell.
    """
    from sqlalchemy import text as _sql
    from ...database import db
    with db.engine.connect() as conn:
        pending = conn.execute(
            _sql(
                "SELECT COUNT(*) FROM catalog_destination_requests "
                "WHERE status = 'pending'"
            )
        ).scalar() or 0
        allowlist = conn.execute(
            _sql("SELECT COUNT(*) FROM catalog_destination_allowlist")
        ).scalar() or 0
    return {
        "pending_tickets": int(pending),
        "allowlisted_destinations": int(allowlist),
    }
