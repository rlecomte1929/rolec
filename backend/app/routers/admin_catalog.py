"""
Admin endpoints for the master service catalog (Phase 2a).

Read-only here; Phase 2c adds the scraper-driven write endpoint and
Phase 2h adds the per-row promote/demote/remove admin UI surface.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..auth_deps import require_admin
from ..services import service_catalog

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
    from ..services import scrape_safety
    return scrape_safety.list_allowlist()


@router.post("/destinations/allowlist")
def add_destination_to_allowlist(
    body: AllowlistAddBody,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    from ..services import scrape_safety
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
    from ..services import scrape_safety
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
    from ..services import scrape_safety
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


# ---------------------------------------------------------------------------
# CATALOG-1: demand-driven coverage worklist
# ---------------------------------------------------------------------------
# Employees who hit an empty provider state upsert into catalog_employee_demand.
# This turns that signal into an admin worklist: the highest-demand
# (category, city) combos that have NO catalog coverage yet, each fillable in
# one action (allowlist + fire the existing LLM scraper). Admin approves; the
# scraper does the research — "let the user work for us".


class FillGapBody(BaseModel):
    category: str
    city: str
    country: str


@router.get("/demand-gaps")
def list_demand_gaps(
    limit: int = Query(50, ge=1, le=200),
    user: Dict[str, Any] = Depends(require_admin),
) -> List[Dict[str, Any]]:
    """
    Cross-company employee demand for (category, city) combos that have NO
    catalog coverage yet, ranked by total demand. Already-allowlisted combos
    are flagged (not hidden) so admin can tell 'queued' from 'uncovered'.
    """
    from sqlalchemy import text as _sql
    from ...database import db
    from ..services import catalog_coverage, scrape_safety

    with db.engine.connect() as conn:
        demand = conn.execute(
            _sql(
                "SELECT category, destination_city AS city, "
                "MAX(destination_country) AS country, "
                "SUM(demand_count) AS demand, "
                "COUNT(DISTINCT company_id) AS companies, "
                "MAX(last_seen_at) AS last_seen_at "
                "FROM catalog_employee_demand "
                "WHERE destination_city IS NOT NULL AND destination_city <> '' "
                "GROUP BY category, destination_city "
                "ORDER BY demand DESC"
            )
        ).mappings().all()

    # Coverage is computed per-city via the canonical coverage report (handles
    # city aliases); cache so each distinct city is queried once.
    coverage_cache: Dict[str, Dict[str, Any]] = {}

    def _have(city: str, category: str) -> int:
        key = (city or "").strip().lower()
        if key not in coverage_cache:
            try:
                coverage_cache[key] = catalog_coverage.report_coverage(city)
            except Exception:
                coverage_cache[key] = {}
        cat = coverage_cache[key].get(category) or {}
        try:
            return int(cat.get("have", 0) or 0)
        except (TypeError, ValueError):
            return 0

    gaps: List[Dict[str, Any]] = []
    for d in demand:
        if _have(d["city"], d["category"]) > 0:
            continue  # already has coverage — not a gap
        last_seen = d["last_seen_at"]
        gaps.append(
            {
                "category": d["category"],
                "city": d["city"],
                "country": d["country"],
                "demand": int(d["demand"] or 0),
                "companies": int(d["companies"] or 0),
                "last_seen_at": last_seen.isoformat() if hasattr(last_seen, "isoformat") else last_seen,
                "allowlisted": scrape_safety.is_destination_allowlisted(d["city"], d["country"]),
            }
        )
    return gaps[:limit]


@router.post("/demand-gaps/fill")
def fill_demand_gap(
    body: FillGapBody,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Allowlist the (city, country) and fire the LLM scraper for (category, city)
    to fill the master catalog. Idempotent on the allowlist; the scraper returns
    [] without raising when disabled / no API key, so scraped_count=0 is a
    valid 'nothing yet' result, not an error.
    """
    from ..services import catalog_scraper, scrape_safety

    city = body.city.strip()
    country = body.country.strip()
    category = body.category.strip()
    if not city or not country or not category:
        raise HTTPException(status_code=400, detail="category, city and country are required")

    try:
        scrape_safety.add_allowlist_entry(
            city=city,
            country=country,
            approved_by_user_id=user["id"],
            notes="Filled from demand worklist (CATALOG-1)",
        )
    except ValueError:
        # Already allowlisted — fine, proceed to scrape.
        pass

    rows = catalog_scraper.populate_destination_catalog(
        category=category,
        destination_city=city,
        country=country,
    )
    return {
        "allowlisted": True,
        "scraped_count": len(rows),
        "category": category,
        "city": city,
        "country": country,
    }


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


class PromoteHrVendorsBody(BaseModel):
    threshold: Optional[int] = Field(
        None, ge=1, description="Distinct-company count to promote at; defaults to CATALOG_HR_PROMOTE_THRESHOLD (2)."
    )
    dry_run: bool = Field(False, description="Preview promotions without writing.")


@router.post("/promote-hr-vendors")
def promote_hr_vendors(
    body: PromoteHrVendorsBody,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """
    [CATALOG-2] Promote HR custom vendors added by >= threshold distinct
    companies for the same (category, city) into the shared master catalog
    with source='hr_promoted'. Idempotent; one-offs and already-catalogued
    vendors are skipped. Pass dry_run=true to preview without writing.
    """
    from ..services import catalog_promotion_service

    try:
        return catalog_promotion_service.promote_hr_vendors(
            threshold=body.threshold,
            dry_run=body.dry_run,
            actor_id=user.get("id"),
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
