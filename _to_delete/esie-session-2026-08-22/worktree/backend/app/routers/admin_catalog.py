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


@router.get("/intake-corridors")
def list_intake_corridors(
    limit: int = Query(50, ge=1, le=200),
    user: Dict[str, Any] = Depends(require_admin),
) -> List[Dict[str, Any]]:
    """
    [CATALOG-4] Proactive companion to /demand-gaps. Aggregates intake
    destinations (wizard_cases) into emerging corridors ranked by intake volume,
    and flags which service categories have NO catalog coverage yet — so admin
    can pre-warm the catalog (allowlist + scrape) BEFORE employees hit an empty
    state, instead of reacting after they do.

    Each returned corridor carries its uncovered categories; admin fills them via
    the same POST /demand-gaps/fill action (category, city, country). No PII:
    only origin/destination geography is read — never employee names.
    """
    from sqlalchemy import text as _sql
    from ...database import db
    from ..services import catalog_coverage, scrape_safety

    with db.engine.connect() as conn:
        corridors = conn.execute(
            _sql(
                "SELECT dest_city AS city, "
                "MAX(dest_country) AS country, "
                "MAX(origin_country) AS top_origin, "
                "COUNT(*) AS intake_count, "
                "MAX(created_at) AS last_intake_at "
                "FROM wizard_cases "
                "WHERE dest_city IS NOT NULL AND dest_city <> '' "
                "GROUP BY dest_city "
                "ORDER BY intake_count DESC"
            )
        ).mappings().all()

    # Coverage is computed per-city via the canonical coverage report (handles
    # city aliases + every registered service category); cache so each distinct
    # city is queried once. Mirrors the /demand-gaps caching pattern.
    coverage_cache: Dict[str, Dict[str, Any]] = {}

    def _uncovered_categories(city: str) -> List[str]:
        key = (city or "").strip().lower()
        if key not in coverage_cache:
            try:
                coverage_cache[key] = catalog_coverage.report_coverage(city)
            except Exception:
                coverage_cache[key] = {}
        out: List[str] = []
        for category, data in (coverage_cache[key] or {}).items():
            # report_coverage emits {"title","items","geo_bound"}; "items" is the
            # coverage count for this city (geo-bound cats) or globally. items==0
            # → genuinely no catalog rows for this corridor → a pre-warm target.
            items = data.get("items") if isinstance(data, dict) else None
            try:
                items_n = int(items or 0)
            except (TypeError, ValueError):
                items_n = 0
            if items_n <= 0:
                out.append(category)
        return sorted(out)

    results: List[Dict[str, Any]] = []
    # Bound the per-city coverage work to the highest-volume corridors.
    for c in corridors[: int(limit)]:
        city = c["city"]
        country = c["country"]
        uncovered = _uncovered_categories(city)
        if not uncovered:
            continue  # corridor is already fully covered — not a pre-warm target
        last_seen = c["last_intake_at"]
        results.append(
            {
                "city": city,
                "country": country,
                "top_origin": c["top_origin"],
                "intake_count": int(c["intake_count"] or 0),
                "last_intake_at": last_seen.isoformat() if hasattr(last_seen, "isoformat") else last_seen,
                "uncovered_categories": uncovered,
                "allowlisted": scrape_safety.is_destination_allowlisted(city, country),
            }
        )
    return results


@router.get("/notification-counts")
def admin_notification_counts(
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Lightweight summary admin uses for nav badges:
      - pending_tickets: HR-opened destination requests waiting on admin
      - allowlisted_destinations: total approved destinations
      - pending_capabilities: supplier capabilities awaiting a vetting decision

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
        try:
            pending_caps = conn.execute(
                _sql(
                    "SELECT COUNT(*) FROM supplier_service_capabilities "
                    "WHERE platform_vetting_status = 'pending'"
                )
            ).scalar() or 0
        except Exception:
            # Column ships with the GAP 1 migration; degrade gracefully if not yet applied.
            pending_caps = 0
    return {
        "pending_tickets": int(pending),
        "allowlisted_destinations": int(allowlist),
        "pending_capabilities": int(pending_caps),
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


# ---------------------------------------------------------------------------
# GAP 5 — real supplier discovery (maps provider → Supplier Registry as pending)
# ---------------------------------------------------------------------------

# Best-effort country name/code → ISO2 for the corridor destinations; unknown
# countries fall back to a global-scope capability (no country_code required).
_COUNTRY_ISO2 = {
    "norway": "NO", "united kingdom": "GB", "united states": "US", "india": "IN",
    "germany": "DE", "singapore": "SG", "united arab emirates": "AE", "france": "FR",
    "netherlands": "NL", "spain": "ES",
}


def _iso2(country: Optional[str]) -> Optional[str]:
    c = (country or "").strip()
    if len(c) == 2:
        return c.upper()
    return _COUNTRY_ISO2.get(c.lower())


def _domain(url: Optional[str]) -> str:
    if not url:
        return ""
    u = url.strip().lower().replace("https://", "").replace("http://", "").replace("www.", "")
    return u.split("/")[0]


class DiscoverBody(BaseModel):
    category: str
    city: str
    country: str


class DiscoverImportItem(BaseModel):
    name: str
    website: Optional[str] = None
    place_id: Optional[str] = None
    formatted_address: Optional[str] = None


class DiscoverImportBody(BaseModel):
    category: str
    city: str
    country: str
    items: List[DiscoverImportItem]


# Quota key for admin-triggered discovery (no company); reuses the per-day
# catalog_scrape_quota cap so enabling a paid provider can't run away on cost.
# NOTE: catalog_scrape_quota.company_id is UUID in prod, so this sentinel MUST be a
# valid UUID — the old "admin-discovery" string raised "invalid input syntax for type
# uuid" (22P02) → 500 on discovery-status/discover. Fixed nil-ish namespace UUID.
_DISCOVERY_QUOTA_KEY = "00000000-0000-0000-0000-0000000ad150"


@router.post("/vendors/refresh-stale")
def refresh_stale_vendors_api(
    dry_run: bool = Query(False),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Trigger the vendor freshness refresh (VEN-11): re-check discovery-sourced
    suppliers via Google Places, refresh ratings, suspend permanently-closed ones."""
    from ..tasks.vendor_freshness_refresh import refresh_stale_vendors
    return {"status": "ok", "stats": refresh_stale_vendors(dry_run=dry_run)}


@router.get("/discovery-status")
def discovery_status(user: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    """Read-only indicator: active provider, whether its key is configured, the
    per-search result cap, and how many searches remain in today's quota."""
    from ..services import maps_discovery, scrape_safety
    status = maps_discovery.provider_status()
    quota = scrape_safety.get_quota_state(_DISCOVERY_QUOTA_KEY)
    status["daily_remaining"] = quota["remaining"]
    status["daily_limit"] = quota["limit"]
    return status


@router.post("/discover")
def discover_suppliers(
    body: DiscoverBody,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Search real businesses for a category+destination. Read-only: returns raw
    results (flagged if already in the catalog); nothing is written until import.
    Cost guardrails: allowlist-gated, results capped (DISCOVERY_MAX_RESULTS), and a
    per-day search quota that is only charged when a provider is actually configured."""
    from ..services import maps_discovery, scrape_safety
    if not scrape_safety.is_destination_allowlisted(body.city, body.country):
        raise HTTPException(status_code=400, detail="Destination is not allowlisted")

    status = maps_discovery.provider_status()
    if not status["configured"]:
        # No provider/key → no external call, no cost, no quota consumed.
        quota = scrape_safety.get_quota_state(_DISCOVERY_QUOTA_KEY)
        return {"results": [], "total": 0, "provider": status["provider"],
                "daily_remaining": quota["remaining"]}

    quota = scrape_safety.check_and_increment_quota(_DISCOVERY_QUOTA_KEY)
    if not quota["allowed"]:
        raise HTTPException(
            status_code=429,
            detail=f"Daily discovery limit reached ({quota['limit']}/day). Try again tomorrow.",
        )
    results = maps_discovery.search_businesses(body.category, body.city, body.country)

    # Flag rows already present in the Supplier Registry (by name or website domain).
    from ..db import SessionLocal
    from ..models import Supplier
    with SessionLocal() as session:
        existing = session.query(Supplier.name, Supplier.website).all()
    names = {(n or "").strip().lower() for n, _ in existing}
    domains = {_domain(w) for _, w in existing if w}
    for r in results:
        dom = _domain(r.get("website"))
        r["already_in_catalog"] = (r.get("name") or "").strip().lower() in names or (bool(dom) and dom in domains)
    return {"results": results, "total": len(results), "provider": status["provider"],
            "daily_remaining": quota["remaining"]}


@router.post("/discover/import")
def import_discovered(
    body: DiscoverImportBody,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Create suppliers + pending capabilities from selected discovery results.
    Imported items land in the vetting queue (source=scraper_discovery)."""
    from ..db import SessionLocal
    from ..models import Supplier
    from ..services import supplier_registry
    iso2 = _iso2(body.country)
    created = 0
    with SessionLocal() as session:
        existing_names = {
            (n or "").strip().lower() for (n,) in session.query(Supplier.name).all()
        }
        for item in body.items:
            if (item.name or "").strip().lower() in existing_names:
                continue
            cap: Dict[str, Any] = {
                "service_category": body.category,
                "city_name": body.city,
                "platform_vetting_status": "pending",
            }
            if iso2:
                cap["coverage_scope_type"] = "city"
                cap["country_code"] = iso2
            else:
                cap["coverage_scope_type"] = "global"
            source_url = (
                f"https://www.google.com/maps/place/?q=place_id:{item.place_id}"
                if item.place_id else None
            )
            try:
                supplier_registry.create_supplier(session, {
                    "name": item.name,
                    "website": item.website,
                    "status": "active",
                    "source": "scraper_discovery",
                    "source_url": source_url,
                    "capabilities": [cap],
                })
                existing_names.add((item.name or "").strip().lower())
                created += 1
            except ValueError:
                continue  # skip individual invalid rows, keep importing the rest
    return {"created": created, "requested": len(body.items)}


# ---------------------------------------------------------------------------
# HR supplier-submission moderation queue (AIQ-1602 Seg 4) — admin reviews and
# approves HR-proposed suppliers into public.suppliers, or rejects them.
# ---------------------------------------------------------------------------


class ResolveSubmissionBody(BaseModel):
    action: str  # 'approve' | 'reject'
    notes: Optional[str] = None


@router.get("/supplier-submissions")
def list_supplier_submissions(
    status: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    from ..services import hr_supplier_submissions

    return {"submissions": hr_supplier_submissions.list_all(status=status)}


@router.patch("/supplier-submissions/{submission_id}")
def resolve_supplier_submission(
    submission_id: str,
    body: ResolveSubmissionBody,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    from ..services import hr_supplier_submissions
    from ..services.supplier_registry import DuplicateSupplierError

    action = (body.action or "").strip().lower()
    try:
        if action == "approve":
            return hr_supplier_submissions.approve(
                submission_id=submission_id, reviewed_by=user.get("id")
            )
        if action == "reject":
            return hr_supplier_submissions.reject(
                submission_id=submission_id,
                reviewed_by=user.get("id"),
                notes=body.notes or "",
            )
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")
    except hr_supplier_submissions.SubmissionNotFound:
        raise HTTPException(status_code=404, detail="submission not found")
    except hr_supplier_submissions.SubmissionNotPending as ex:
        raise HTTPException(status_code=409, detail=str(ex))
    except DuplicateSupplierError as ex:
        raise HTTPException(status_code=409, detail=str(ex))
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
