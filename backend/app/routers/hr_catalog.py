"""
HR-side catalog curation endpoints (Phase 2d).

GET   /api/hr/catalog/curation         — combined view: master items
                                          for the (category, city) joined
                                          with HR's selection state
POST  /api/hr/catalog/curation/select  — bulk toggle selected on master rows
POST  /api/hr/catalog/curation/custom  — add an HR custom vendor
DELETE /api/hr/catalog/curation/custom/{id} — remove an HR custom vendor

All routes require HR or Admin and are tenant-scoped to caller's company.
Audit trail goes via the relopass_audit_row trigger on the table.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..auth_deps import require_admin_or_hr
from ...database import db
from ..services import service_catalog, vendor_curation

router = APIRouter(prefix="/api/hr/catalog", tags=["hr_catalog"])
logger = logging.getLogger(__name__)


def _caller_company_id(user: Dict[str, Any]) -> str:
    profile = db.get_profile_record(user.get("id"))
    company_id = (profile or {}).get("company_id") or user.get("company")
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail="No company linked to this profile — HR curation needs a tenant.",
        )
    return company_id


def _caller_company_id_optional(user: Dict[str, Any]) -> Optional[str]:
    """Same lookup as _caller_company_id but returns None instead of 403.

    Used by read-only "dashboard widget" endpoints (notification badges,
    summary counts) that should render gracefully for admins / unlinked
    users rather than 403-ing every HR page load."""
    profile = db.get_profile_record(user.get("id"))
    company_id = (profile or {}).get("company_id") or user.get("company")
    return str(company_id) if company_id else None


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CurationRow(BaseModel):
    kind: str  # "master" | "custom"
    selection_id: Optional[str] = None
    master_item_id: Optional[str] = None
    name: str
    selected: bool
    attributes: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None  # master row source (scraper / manual / seed / hr_promoted)
    city: Optional[str] = None
    country: Optional[str] = None


class CurationView(BaseModel):
    company_id: str
    category: str
    destination_city: Optional[str]
    rows: List[CurationRow]


class SelectToggle(BaseModel):
    master_item_id: str
    selected: bool


class BulkSelectBody(BaseModel):
    category: str
    destination_city: Optional[str] = None
    country: Optional[str] = None
    toggles: List[SelectToggle]


class CustomVendorBody(BaseModel):
    category: str
    name: str = Field(..., min_length=1, max_length=200)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    destination_city: Optional[str] = None
    country: Optional[str] = None
    display_order: int = 0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/curation", response_model=CurationView)
def get_curation_view(
    category: str = Query(..., min_length=1),
    destination_city: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """
    Combined view HR uses to curate one category × city. Returns:
    - Every admin master item for (category, city) with the HR selection state
      attached (or "selected=true" by default if HR hasn't decided yet).
    - Every HR custom vendor row for the same scope.
    """
    company_id = _caller_company_id(user)
    # Match the master plugins' geo-bound vs geo-agnostic split: when the
    # category has no rows tagged with a city, every row applies everywhere
    # (e.g. movers / banks). Filtering strictly on city would hide them and
    # leave HR with "0 items" for categories that in fact have a full list.
    all_active = service_catalog.list_items(
        category=category,
        active_only=True,
        limit=200,
    )
    has_geo_rows = any(m.get("city") for m in all_active)
    if has_geo_rows and destination_city:
        master_items = [m for m in all_active if m.get("city") == destination_city]
    else:
        master_items = all_active
    selections = vendor_curation.list_curation(
        company_id=company_id,
        category=category,
        destination_city=destination_city,
    )

    # Index HR selections by master_item_id (master toggles) and a list of customs.
    selection_by_master: Dict[str, Dict[str, Any]] = {}
    customs: List[Dict[str, Any]] = []
    for s in selections:
        if s.get("master_item_id"):
            selection_by_master[s["master_item_id"]] = s
        elif s.get("custom_item_json"):
            customs.append(s)

    rows: List[CurationRow] = []
    for m in master_items:
        sel = selection_by_master.get(m["id"])
        rows.append(
            CurationRow(
                kind="master",
                selection_id=sel.get("id") if sel else None,
                master_item_id=m["id"],
                name=m["name"],
                # Default to False (hidden) until HR explicitly approves —
                # the strict authority model: "the employee can only pick
                # from the list pre-selected and validated by HR." Until HR
                # ticks an item, the employee does not see it. The empty
                # employee state is rendered as "HR is finalizing providers"
                # by Phase 2c's filter.
                selected=bool(sel["selected"]) if sel else False,
                attributes=m.get("attributes_json") or {},
                source=m.get("source"),
                city=m.get("city"),
                country=m.get("country"),
            )
        )
    for c in customs:
        payload = c.get("custom_item_json") or {}
        rows.append(
            CurationRow(
                kind="custom",
                selection_id=c["id"],
                master_item_id=None,
                name=str(payload.get("name") or "(unnamed)"),
                selected=bool(c["selected"]),
                attributes={k: v for k, v in payload.items() if k != "name"},
                source=None,
                city=c.get("destination_city"),
                country=c.get("country"),
            )
        )
    return {
        "company_id": company_id,
        "category": category,
        "destination_city": destination_city,
        "rows": [r.model_dump() for r in rows],
    }


@router.post("/curation/select")
def bulk_select(
    body: BulkSelectBody,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """Toggle selected on/off for one or more master rows in one call."""
    company_id = _caller_company_id(user)
    actor_id = user["id"]
    updated = []
    for t in body.toggles:
        row = vendor_curation.upsert_master_selection(
            company_id=company_id,
            category=body.category,
            master_item_id=t.master_item_id,
            selected=t.selected,
            destination_city=body.destination_city,
            country=body.country,
            actor_user_id=actor_id,
        )
        updated.append(row)
    return {"updated": len(updated), "rows": updated}


@router.post("/curation/custom")
def add_custom(
    body: CustomVendorBody,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """HR adds a vendor not in the admin master."""
    company_id = _caller_company_id(user)
    actor_id = user["id"]
    try:
        row = vendor_curation.add_custom_vendor(
            company_id=company_id,
            category=body.category,
            name=body.name,
            attributes=body.attributes,
            destination_city=body.destination_city,
            country=body.country,
            display_order=body.display_order,
            actor_user_id=actor_id,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    return row


@router.delete("/curation/custom/{row_id}")
def delete_custom(
    row_id: str,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    company_id = _caller_company_id(user)
    try:
        ok = vendor_curation.delete_custom_vendor(company_id=company_id, row_id=row_id)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    if not ok:
        raise HTTPException(status_code=404, detail="Custom vendor not found")
    return {"deleted": True, "id": row_id}


# ---------------------------------------------------------------------------
# Phase 2b-secured: HR-initiated scraper trigger with allowlist + quota gates
# ---------------------------------------------------------------------------


class PopulateWithAiBody(BaseModel):
    category: str = Field(..., min_length=1)
    destination_city: str = Field(..., min_length=1)
    country: str = Field(..., min_length=1)


@router.post("/populate-with-ai")
def populate_with_ai(
    body: PopulateWithAiBody,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """
    HR-initiated catalog scrape. Layered safety:

      L4 allowlist  → off-allowlist requests open a ticket instead of
                      burning tokens (returns 202 + {"status": "pending_admin_approval"})
      L3 quota      → 429 when the company has exceeded today's daily cap
      L1 already-populated check happens inside catalog_scraper —
                      callers won't re-burn tokens for a populated slot
      L7 audit      → every dispatch + every ticket open writes an audit_logs row
    """
    from ..services import scrape_safety, catalog_scraper

    company_id = _caller_company_id(user)
    actor_id = user["id"]
    city = body.destination_city.strip()
    country = body.country.strip()

    # L4 — allowlist gate
    if not scrape_safety.is_destination_allowlisted(city, country):
        ticket = scrape_safety.open_destination_request(
            city=city,
            country=country,
            category=body.category,
            requested_by_user_id=actor_id,
            company_id=company_id,
        )
        return {
            "status": "pending_admin_approval",
            "request": ticket,
            "message": (
                f"{city}, {country} isn't on our supported destinations yet. "
                "We've notified our admin team — you'll see it appear here once approved."
            ),
        }

    # L3 — quota gate (atomic check + increment so concurrent calls don't race)
    quota = scrape_safety.check_and_increment_quota(company_id)
    if not quota["allowed"]:
        raise HTTPException(
            status_code=429,
            detail={
                "message": (
                    f"Daily catalog-scrape quota of {quota['limit']} reached "
                    f"for your company. Try again tomorrow (UTC) or contact admin."
                ),
                "quota": quota,
            },
        )

    # L1 short-circuit lives inside populate_destination_catalog itself.
    rows = catalog_scraper.populate_destination_catalog(
        category=body.category,
        destination_city=city,
        country=country,
    )
    return {
        "status": "completed",
        "category": body.category,
        "destination_city": city,
        "country": country,
        "inserted": len(rows),
        "quota": quota,
    }


@router.get("/scrape-quota")
def get_scrape_quota(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """Return today's quota state for the caller's company. Used by the UI."""
    from ..services import scrape_safety
    return scrape_safety.get_quota_state(_caller_company_id(user))


@router.get("/destination-requests")
def list_my_destination_requests(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> List[Dict[str, Any]]:
    """HR sees the tickets they (or their company) have opened."""
    from ..services import scrape_safety
    return scrape_safety.list_destination_requests(
        company_id=_caller_company_id(user),
        limit=100,
    )


class DestinationRequestResolve(BaseModel):
    status: str = Field(..., description="Must be 'approved' or 'rejected'")
    notes: Optional[str] = Field(None, max_length=500)


@router.patch("/destination-requests/{request_id}")
def resolve_destination_request_hr(
    request_id: str,
    body: DestinationRequestResolve,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """
    HR approves or rejects a destination request from their company.

    When approved the destination (city, country) is automatically added to the
    catalog_destination_allowlist so the AI catalog can be populated for that
    city in future sessions.

    Only requests that belong to the caller's company can be resolved here;
    cross-company access returns 404.
    """
    from ..services import scrape_safety

    if body.status not in ("approved", "rejected"):
        raise HTTPException(status_code=422, detail="status must be 'approved' or 'rejected'")

    company_id = _caller_company_id(user)

    # Verify the request belongs to this company before allowing resolution
    company_reqs = scrape_safety.list_destination_requests(company_id=company_id, limit=500)
    matching = next((r for r in company_reqs if r["id"] == request_id), None)
    if not matching:
        raise HTTPException(status_code=404, detail="Destination request not found for your company")

    try:
        result = scrape_safety.resolve_destination_request(
            request_id=request_id,
            new_status=body.status,
            actor_user_id=str(user["id"]),
            notes=body.notes,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Destination request not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    # If approved, add city+country to the destination allowlist so the catalog
    # can be populated for future HR requests
    if body.status == "approved":
        try:
            scrape_safety.add_allowlist_entry(
                city=matching["city"],
                country=matching["country"],
                approved_by_user_id=str(user["id"]),
                notes=f"Approved via HR portal (request_id={request_id})",
            )
            logger.info(
                "HR approved destination request %s — %s, %s added to allowlist",
                request_id, matching["city"], matching["country"],
            )
        except Exception:
            # Non-fatal: the request was resolved successfully even if allowlist update failed
            logger.exception(
                "Failed to add allowlist entry after HR approval request_id=%s", request_id
            )

    return result


# ---------------------------------------------------------------------------
# Phase 2b — destination-scoped flow (replaces single-category as the primary path)
# ---------------------------------------------------------------------------

# Sentinel category used on tickets that ask the admin to allowlist a brand-new
# destination ("populate ALL services here"). Distinct from any real category
# key so the admin queue UI can render it as "All services".
ALL_CATEGORIES_SENTINEL = "_all_categories"


@router.get("/destinations")
def list_allowlisted_destinations(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> List[Dict[str, Any]]:
    """
    HR-readable list of (city, country) the system supports for AI scraping.
    Frontend uses this to render a dropdown — HR can only pick supported
    destinations, never type a free-form string. Anything else goes through
    the "Request a new destination" ticket flow.
    """
    from ..services import scrape_safety
    return scrape_safety.list_allowlist()


class PopulateDestinationBody(BaseModel):
    destination_city: str = Field(..., min_length=1)
    country: str = Field(..., min_length=1)


@router.post("/populate-destination-with-ai")
def populate_destination_with_ai(
    body: PopulateDestinationBody,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """
    Destination-level scraper trigger — populates ALL service categories
    for the (city, country) in one HR click, with the same safety layers
    as the per-category endpoint:

      L4 allowlist → off-list opens a SINGLE ticket (category sentinel
                     "_all_categories") and returns 202-style pending,
                     no LLM calls.
      L3 quota     → each category that actually fires the LLM counts as
                     1 against the daily cap. Categories already populated
                     short-circuit (L1) and do NOT increment the quota.
      L1 already-populated → skipped per-category.
    """
    from ..services import scrape_safety, catalog_scraper
    from ..recommendations.registry import list_categories

    company_id = _caller_company_id(user)
    actor_id = user["id"]
    city = body.destination_city.strip()
    country = body.country.strip()

    # L4 — allowlist
    if not scrape_safety.is_destination_allowlisted(city, country):
        ticket = scrape_safety.open_destination_request(
            city=city,
            country=country,
            category=ALL_CATEGORIES_SENTINEL,
            requested_by_user_id=actor_id,
            company_id=company_id,
        )
        return {
            "status": "pending_admin_approval",
            "request": ticket,
            "message": (
                f"{city}, {country} isn't on our supported destinations yet. "
                "We've notified our admin team — once approved, you can populate "
                "every service category in one click."
            ),
        }

    # Iterate all known categories. Each that actually calls the LLM counts
    # against quota; each that hits the L1 short-circuit (already populated)
    # is skipped silently and does NOT charge quota.
    categories = [c["key"] for c in list_categories()]
    results: List[Dict[str, Any]] = []
    populated = 0
    skipped_existing = 0
    quota_blocked = 0
    total_inserted = 0
    last_quota: Optional[Dict[str, Any]] = None

    # Cheap config gate: if the scraper is disabled OR no API key, no
    # category will actually invoke the LLM. Don't charge quota or even
    # call the scraper module — return everything as "scraper_disabled"
    # so the UX message stays honest.
    scraper_runnable = catalog_scraper._enabled() and bool(os.getenv("OPENAI_API_KEY"))

    for cat in categories:
        # L1 pre-check: if rows already exist, mark as skipped without
        # touching quota or the scraper at all.
        from ..services import service_catalog
        if service_catalog.count_by_category_city(cat, city) > 0:
            skipped_existing += 1
            results.append({"category": cat, "status": "skipped_existing", "inserted": 0})
            continue

        if not scraper_runnable:
            # Scraper is off (or unconfigured) — don't charge quota for a
            # call that physically can't happen. The UI shows this state
            # via the per-category breakdown.
            results.append({"category": cat, "status": "scraper_disabled", "inserted": 0})
            continue

        # L3 — quota gate. We only get here if the scraper actually CAN
        # call the LLM. If we've burned through the cap mid-loop, remaining
        # categories return quota_blocked and we stop incrementing.
        quota = scrape_safety.check_and_increment_quota(company_id)
        last_quota = quota
        if not quota["allowed"]:
            quota_blocked += 1
            results.append({"category": cat, "status": "quota_blocked", "inserted": 0})
            continue

        rows = catalog_scraper.populate_destination_catalog(
            category=cat,
            destination_city=city,
            country=country,
        )
        if rows:
            populated += 1
            total_inserted += len(rows)
            results.append({"category": cat, "status": "populated", "inserted": len(rows)})
        else:
            # Scraper returned 0 (LLM failed, disabled, no API key) — quota was
            # incremented; treat as failed for clarity.
            results.append({"category": cat, "status": "scraper_returned_empty", "inserted": 0})

    if last_quota is None:
        # Every category short-circuited (everything already populated).
        last_quota = scrape_safety.get_quota_state(company_id)

    return {
        "status": "completed",
        "destination_city": city,
        "country": country,
        "categories_total": len(categories),
        "categories_populated": populated,
        "categories_skipped_existing": skipped_existing,
        "categories_quota_blocked": quota_blocked,
        "total_inserted": total_inserted,
        "per_category": results,
        "quota": last_quota,
    }


@router.get("/employee-demand")
def list_employee_demand(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> List[Dict[str, Any]]:
    """
    HR-side view of which (category, destination) combos employees are
    currently waiting on. Each row records the most-recent employee who
    hit the "HR is finalizing" empty state, plus how many times that
    combo has been seen across the company.
    """
    from ..services import employee_demand
    return employee_demand.list_demand_for_company(_caller_company_id(user))


@router.get("/notification-counts")
def hr_notification_counts(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """
    Lightweight summary HR uses to render nav badges:
      - employees_waiting: total demand_count across pending demand rows
      - destinations_with_demand: distinct (category, city) combos
      - pending_admin_tickets: tickets HR opened that are still pending admin

    Computed via SQL aggregates in a single connection. The earlier version
    materialised up to 500 demand rows and ran one vendor_curation lookup per
    row (N+1) — under prod load that exhausted the SQLAlchemy pool and made
    the dashboard time out (Render incident 2026-05-07).
    """
    from sqlalchemy import text as _sql
    company_id = _caller_company_id_optional(user)
    if not company_id:
        # Admin / unlinked user: zeroed badges instead of 403 noise in
        # every HR page console.
        return {
            "employees_waiting": 0,
            "destinations_with_demand": 0,
            "pending_admin_tickets": 0,
        }

    # NOT EXISTS mirrors employee_demand._has_curation: hide demand rows where
    # HR already has at least one curated vendor (master selected, or custom).
    not_curated = (
        " NOT EXISTS ("
        "   SELECT 1 FROM company_vendor_selections cvs"
        "   WHERE cvs.company_id = ed.company_id"
        "     AND cvs.category = ed.category"
        "     AND (cvs.destination_city = ed.destination_city"
        "          OR cvs.destination_city IS NULL)"
        "     AND (cvs.custom_item_json IS NOT NULL"
        "          OR (cvs.master_item_id IS NOT NULL AND cvs.selected = TRUE))"
        " )"
    )

    with db.engine.connect() as conn:
        sums = conn.execute(
            _sql(
                "SELECT COALESCE(SUM(ed.demand_count), 0) AS waiting "
                "FROM catalog_employee_demand ed "
                "WHERE ed.company_id = :co AND" + not_curated
            ),
            {"co": company_id},
        ).mappings().first()
        distinct_count = conn.execute(
            _sql(
                "SELECT COUNT(*) FROM ("
                "  SELECT DISTINCT ed.category, ed.destination_city"
                "  FROM catalog_employee_demand ed"
                "  WHERE ed.company_id = :co AND" + not_curated +
                ") sub"
            ),
            {"co": company_id},
        ).scalar() or 0
        pending = conn.execute(
            _sql(
                "SELECT COUNT(*) FROM catalog_destination_requests "
                "WHERE status = 'pending' AND company_id = :co"
            ),
            {"co": company_id},
        ).scalar() or 0

    return {
        "employees_waiting": int((sums or {}).get("waiting") or 0),
        "destinations_with_demand": int(distinct_count),
        "pending_admin_tickets": int(pending),
    }
