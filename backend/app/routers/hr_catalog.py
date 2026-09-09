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
from pydantic import BaseModel, Field, field_validator

from ..auth_deps import require_admin_or_hr
from ...database import db
from ..db import SessionLocal
from ..services import service_catalog, vendor_curation
# The canonicaliser that decides whether two spellings are the same city. Imported
# from the module that owns it so this filter and list_curation cannot drift apart
# again — they disagreeing is the bug this fixes.
from ..services.vendor_curation import _canon_city
from ..services.audit_log_service import (
    ACTION_DELETE,
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
    insert_audit_log,
)

router = APIRouter(prefix="/api/hr/catalog", tags=["hr_catalog"])


def _audit_catalog(actor_id, entity_id, action: str, event: str,
                   extra: "Optional[Dict[str, Any]]" = None) -> None:
    """[AIQ-932b] Fail-soft canonical audit for an HR vendor-curation mutation.
    vendor_curation records created_by on the row but writes no audit_logs row;
    audit runs here in its own SessionLocal txn. (destination-request resolve is
    already audited inside scrape_safety, so it is not re-audited here.)"""
    try:
        with SessionLocal() as asession:
            insert_audit_log(
                asession.connection(),
                entity_type="company_vendor_selection",
                entity_id=str(entity_id),
                action_type=action,
                actor_type=ACTOR_HUMAN,
                actor_id=actor_id,
                new_value={"event": event, **(extra or {})},
            )
            asession.commit()
    except Exception:
        logger.exception("audit: catalog %s id=%s", event, entity_id)
logger = logging.getLogger(__name__)


def _caller_company_id(user: Dict[str, Any]) -> str:
    uid = user.get("id")
    # hr_users-first: legacy/text HR ids (e.g. seed-hr-testingapril) have a NULL
    # profiles.company_id but a valid hr_users row — profiles-only would 403 them.
    company_id = (db.get_hr_company_id(uid) if uid else None) or (db.get_profile_record(uid) or {}).get("company_id") or user.get("company")
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
    uid = user.get("id")
    company_id = (db.get_hr_company_id(uid) if uid else None) or (db.get_profile_record(uid) or {}).get("company_id") or user.get("company")
    return str(company_id) if company_id else None


def _is_verified(attributes: Any) -> bool:
    """Read the human-authoritative `verified` flag off a catalog item's attributes.

    Tolerant of the shapes the column has actually held — a real bool, or the string "true"
    from a JSON round-trip — and defaults to False. Absence means "nobody has signed this
    off", which is exactly the state the UI must flag, so an unreadable value must never
    read as verified.
    """
    if not isinstance(attributes, dict):
        return False
    raw = attributes.get("verified")
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() == "true"


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
    # Lifted out of `attributes` so the UI does not have to reach into a free-form blob to
    # decide whether to show the "Pending ReloPass verification" flag. Human-authoritative:
    # nothing in the serving path ever sets this true, it only reads what ops signed off.
    verified: bool = False

    # The id fields come straight from the DB. Under Postgres (prod) uuid
    # columns are returned as `uuid.UUID` objects, but under SQLite (tests)
    # they are plain strings — so a bare `str` annotation passes tests yet
    # raises a Pydantic `string_type` error in prod, 500ing the curation view
    # for any category that has master vendors. Coerce non-null ids to str.
    @field_validator("selection_id", "master_item_id", mode="before")
    @classmethod
    def _coerce_id_to_str(cls, v: Any) -> Optional[str]:
        return str(v) if v is not None else None


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
    country: Optional[str] = Query(
        None,
        min_length=2,
        max_length=2,
        description="ISO alpha-2 destination country. Scopes the catalog proposal to vendors "
                    "in that country. Omitted = every country, the pre-existing behaviour.",
    ),
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """
    Combined view HR uses to curate one category × city. Returns:
    - Every admin master item for (category, city) with the HR selection state
      attached. A master HR has not decided on comes back ``selected=false`` —
      the strict authority model, spelled out at the assignment below: an item
      the employee can pick must have been ticked by HR first.
    - Every HR custom vendor row for the same scope.

    `country` scopes the catalog side to one destination. Without it the proposal spans every
    country in the catalog, which is why a case bound for Ireland could not surface Ireland's
    vendors as a destination list — the filter simply was not offered. `service_catalog.list_items`
    has always accepted the argument; this route just never passed it.

    [AIQ-1904] This docstring used to claim the opposite of the line above — ``selected=true``
    by default "if HR hasn't decided yet" — while the code has always defaulted to False.
    Measured against production 2026-08-22 as hr@testingapril.com: ``category=movers``
    returns 105 rows, **105 of them ``selected: false`` with ``selection_id: null``**.
    Reading the old sentence, an engineer would conclude a fresh company already had its
    catalog curated and that employees could see it; in fact they get the "HR is finalizing
    providers" empty state until HR ticks something (or AIQ-1903's seed writes explicit
    rows). That is a deliberate design, and this line was the only thing contradicting it.
    """
    # This router is unit-tested by calling the function directly rather than through FastAPI,
    # so an unfilled `Query(...)` default arrives as a Query object, not None. Left unnormalised
    # it is truthy, reaches `list_items` and dies at the SQL bind with
    # "type 'Query' is not supported". Coerce anything that is not a real string to None.
    country = country if isinstance(country, str) else None
    company_id = _caller_company_id(user)
    # Match the master plugins' geo-bound vs geo-agnostic split: when the
    # category has no rows tagged with a city, every row applies everywhere
    # (e.g. movers / banks). Filtering strictly on city would hide them and
    # leave HR with "0 items" for categories that in fact have a full list.
    # `limit` is applied BEFORE the city filter below, so a category that outgrows it loses
    # whole cities silently — no error, just an empty curation screen. Measured 2026-08-23:
    # legal_admin held 183 active items against the old cap of 200 (92%). Raised well clear
    # of the largest category rather than left as a tripwire one scrape away from firing.
    all_active = service_catalog.list_items(
        category=category,
        country=country,
        active_only=True,
        limit=2000,
    )
    has_geo_rows = any(m.get("city") for m in all_active)
    if has_geo_rows and destination_city:
        # Canonical comparison, NOT `==`. This filter was a raw string equality while
        # `vendor_curation.list_curation` — called a few lines below, in the SAME request —
        # canonicalises the city for exactly the stated reason (AIQ-1457: "so casing/
        # whitespace/diacritic differences between HR's picker city and the employee's
        # intake city don't hide curated vendors"). The two halves of one screen disagreed
        # about what a city IS.
        #
        # It cost a real user 29 vendors: the destination allowlist held Dublin as both
        # 'Dublin' and 'dublin', the picker offered both, and choosing the lower-cased one
        # returned zero master items while 29 sat curated and selected=true underneath.
        want = _canon_city(destination_city)
        master_items = [m for m in all_active if _canon_city(m.get("city")) == want]
    else:
        master_items = all_active
    # Defensive de-dupe by name: two seed batches inserted the same vendors with
    # different external_ids (e.g. 'm-2' vs a uuid), so the master list showed
    # each vendor twice. Collapse by case-insensitive name, first occurrence wins
    # (list_items is ordered updated_at DESC). A prefer-selected pass below would
    # need the selection map, which isn't built yet — first-wins is sufficient
    # because the data cleanup deactivates the unselected duplicate.
    _seen_names: set = set()
    _deduped: List[Dict[str, Any]] = []
    for m in master_items:
        key = (m.get("name") or "").strip().lower()
        if key in _seen_names:
            continue
        _seen_names.add(key)
        _deduped.append(m)
    master_items = _deduped
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
                verified=_is_verified(m.get("attributes_json")),
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
                # An HR-added vendor has by definition not been through ReloPass accreditation,
                # so it is never platform-verified regardless of what the payload claims.
                verified=False,
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
    rejected = []
    for t in body.toggles:
        try:
            row = vendor_curation.upsert_master_selection(
                company_id=company_id,
                category=body.category,
                master_item_id=t.master_item_id,
                selected=t.selected,
                destination_city=body.destination_city,
                country=body.country,
                actor_user_id=actor_id,
            )
        except vendor_curation.CountryMismatch as exc:
            # Per toggle, not per batch. HR saves many rows at once; discarding the whole
            # save because one vendor is in the wrong country would be a worse bug than the
            # one this guard exists to fix. The rejects are returned so nothing is silent.
            rejected.append({"master_item_id": t.master_item_id, "reason": str(exc)})
            continue
        updated.append(row)
    if updated:
        _audit_catalog(actor_id, company_id, ACTION_UPDATE, "vendor_selections_updated",
                       {"category": body.category, "count": len(updated)})
    if rejected:
        logger.warning(
            "bulk_select: %d toggle(s) rejected on country mismatch (company=%s category=%s)",
            len(rejected), company_id, body.category,
        )
    # `rejected` is additive — the existing client reads `updated`/`rows` and is unaffected.
    return {"updated": len(updated), "rows": updated, "rejected": rejected}


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
    _audit_catalog(actor_id, (row or {}).get("id"), ACTION_INSERT, "custom_vendor_added",
                   {"category": body.category, "name": body.name})
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
    _audit_catalog(user.get("id"), row_id, ACTION_DELETE, "custom_vendor_deleted")
    return {"deleted": True, "id": row_id}


# ---------------------------------------------------------------------------
# Phase 2b-secured: HR-initiated scraper trigger with allowlist + quota gates
# ---------------------------------------------------------------------------


class PopulateWithAiBody(BaseModel):
    category: str = Field(..., min_length=1)
    destination_city: str = Field(..., min_length=1)
    country: str = Field(..., min_length=1)


class VendorDiscoverBody(BaseModel):
    category: str = Field(..., min_length=1)
    destination_city: str = Field(..., min_length=1)
    country: str = Field(..., min_length=1)


@router.post("/discover")
def discover_vendors_for_city(
    body: VendorDiscoverBody,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """HR-triggered vendor discovery (VEN-10): fetch the top verified vendors from
    the maps provider for (category, city), quality-gate + rank them, and upsert
    into the master catalog so they appear in this HR team's curation view. Same
    allowlist + quota safety as populate-with-ai; off by default ($0)."""
    from ..services import maps_discovery, scrape_safety

    company_id = _caller_company_id(user)
    actor_id = user["id"]
    city = body.destination_city.strip()
    country = body.country.strip()

    # L4 — allowlist gate (off-list opens a ticket instead of spending)
    if not scrape_safety.is_destination_allowlisted(city, country):
        ticket = scrape_safety.open_destination_request(
            city=city, country=country, category=body.category,
            requested_by_user_id=actor_id, company_id=company_id,
        )
        return {
            "status": "pending_admin_approval", "request": ticket, "vendors": [], "count": 0,
            "message": (f"{city}, {country} isn't on our supported destinations yet. "
                        "We've notified our admin team — you'll see it appear here once approved."),
        }

    # Provider not configured → no external call, no cost, no quota consumed.
    if not maps_discovery.provider_status()["configured"]:
        return {"vendors": [], "count": 0, "message": "Vendor discovery isn't enabled yet."}

    # L3 — quota gate (atomic)
    quota = scrape_safety.check_and_increment_quota(company_id)
    if not quota["allowed"]:
        raise HTTPException(
            status_code=429,
            detail=f"Daily discovery limit reached ({quota['limit']}/day). Try again tomorrow.",
        )

    from ..services.vendor_discovery.orchestrator import discover_to_catalog
    vendors = discover_to_catalog(body.category, city, country)
    return {
        "vendors": vendors,
        "count": len(vendors),
        "destination_city": city,
        "category": body.category,
        "message": (None if vendors else
                    f"No verified vendors found for {body.category} in {city}. The city may not "
                    "have enough reviewed businesses yet."),
    }


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
    # Defensive: a scraper/DB failure must degrade to a 200 error status, not a raw 500.
    try:
        rows = catalog_scraper.populate_destination_catalog(
            category=body.category,
            destination_city=city,
            country=country,
        )
        # Backfill service-type tags onto any existing vendors that lack them, so a
        # re-click of "Populate" makes an already-populated category filterable. The
        # call no-ops (no LLM cost) when every vendor is already tagged or when the
        # populate above just inserted fresh (already-tagged) rows.
        backfill = catalog_scraper.backfill_service_types(
            category=body.category, destination_city=city, country=country,
        )
    except Exception:
        logger.exception(
            "populate-with-ai: category=%s city=%s country=%s failed", body.category, city, country
        )
        return {
            "status": "error",
            "category": body.category,
            "destination_city": city,
            "country": country,
            "inserted": 0,
            "service_types_tagged": 0,
            "quota": quota,
        }
    return {
        "status": "completed",
        "category": body.category,
        "destination_city": city,
        "country": country,
        "inserted": len(rows),
        "service_types_tagged": backfill.get("tagged", 0),
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
        # Per-category isolation: any unexpected error (a DB hiccup in
        # count_by_category_city, quota, or the scraper's outer path) must NOT
        # abort the whole batch and 500 the request — record it and continue.
        try:
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
        except Exception:
            logger.exception(
                "populate-destination: category=%s city=%s country=%s failed", cat, city, country
            )
            results.append({"category": cat, "status": "error", "inserted": 0})
            continue

    if last_quota is None:
        # Every category short-circuited (everything already populated).
        last_quota = scrape_safety.get_quota_state(company_id)

    # Backfill service-type tags onto existing vendors that lack them, across all
    # categories. This is what makes already-populated destinations (the common
    # case — "Oslo already has master vendors") filterable on a re-click. Each
    # call no-ops without an LLM hit when its category is already fully tagged or
    # was just freshly populated (fresh rows arrive pre-tagged).
    total_tagged = 0
    for cat in categories:
        try:
            bf = catalog_scraper.backfill_service_types(
                category=cat, destination_city=city, country=country,
            )
            total_tagged += bf.get("tagged", 0)
        except Exception:
            logger.exception(
                "populate-destination backfill: category=%s city=%s country=%s failed",
                cat, city, country,
            )

    return {
        "status": "completed",
        "destination_city": city,
        "country": country,
        "categories_total": len(categories),
        "categories_populated": populated,
        "categories_skipped_existing": skipped_existing,
        "categories_quota_blocked": quota_blocked,
        "total_inserted": total_inserted,
        "service_types_tagged": total_tagged,
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
        row = conn.execute(
            _sql(
                "SELECT "
                "  COALESCE(("
                "    SELECT SUM(ed.demand_count) FROM catalog_employee_demand ed "
                "    WHERE ed.company_id = :co AND" + not_curated +
                "  ), 0) AS waiting, "
                "  (SELECT COUNT(*) FROM ("
                "    SELECT DISTINCT ed.category, ed.destination_city"
                "    FROM catalog_employee_demand ed"
                "    WHERE ed.company_id = :co AND" + not_curated +
                "  ) sub) AS distinct_pairs, "
                "  (SELECT COUNT(*) FROM catalog_destination_requests "
                "   WHERE status = 'pending' AND company_id = :co) AS pending"
            ),
            {"co": company_id},
        ).mappings().first()

    return {
        "employees_waiting": int((row or {}).get("waiting") or 0),
        "destinations_with_demand": int((row or {}).get("distinct_pairs") or 0),
        "pending_admin_tickets": int((row or {}).get("pending") or 0),
    }


@router.get("/vendor-assignments/pending")
def list_pending_vendor_assignments(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """
    Returns demand rows where HR has not yet curated a vendor for the employee.
    Used by the vendor curation widget to show "pending vendor assignments".
    Resolves B16 — endpoint was missing (404).
    """
    from sqlalchemy import text as _sql
    company_id = _caller_company_id_optional(user)
    if not company_id:
        return {"count": 0, "items": []}
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                _sql(
                    "SELECT ed.id, ed.category, ed.destination_city, ed.demand_count, "
                    "       ed.last_employee_id, ed.created_at "
                    "FROM catalog_employee_demand ed "
                    "WHERE ed.company_id = :co "
                    "  AND NOT EXISTS ("
                    "    SELECT 1 FROM company_vendor_selections cvs"
                    "    WHERE cvs.company_id = ed.company_id"
                    "      AND cvs.category = ed.category"
                    "      AND (cvs.destination_city = ed.destination_city"
                    "           OR cvs.destination_city IS NULL)"
                    "      AND (cvs.custom_item_json IS NOT NULL"
                    "           OR (cvs.master_item_id IS NOT NULL AND cvs.selected = TRUE))"
                    "  ) "
                    "ORDER BY ed.demand_count DESC LIMIT 50"
                ),
                {"co": company_id},
            ).mappings().all()
        items = []
        for r in rows:
            d = dict(r)
            for k, v in d.items():
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
            items.append(d)
        return {"count": len(items), "items": items}
    except Exception:
        logger.exception("list_pending_vendor_assignments failed company_id=%s", company_id)
        return {"count": 0, "items": []}


@router.get("/employees/waiting")
def employees_waiting_count(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """
    Returns the count of employees waiting for vendor curation (uncurated demand).
    Thin wrapper over the employees_waiting field in notification-counts.
    Resolves B16 — endpoint was missing (404).
    """
    from sqlalchemy import text as _sql
    company_id = _caller_company_id_optional(user)
    if not company_id:
        return {"count": 0}
    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                _sql(
                    "SELECT COALESCE(SUM(ed.demand_count), 0) AS waiting "
                    "FROM catalog_employee_demand ed "
                    "WHERE ed.company_id = :co "
                    "  AND NOT EXISTS ("
                    "    SELECT 1 FROM company_vendor_selections cvs"
                    "    WHERE cvs.company_id = ed.company_id"
                    "      AND cvs.category = ed.category"
                    "      AND (cvs.destination_city = ed.destination_city"
                    "           OR cvs.destination_city IS NULL)"
                    "      AND (cvs.custom_item_json IS NOT NULL"
                    "           OR (cvs.master_item_id IS NOT NULL AND cvs.selected = TRUE))"
                    "  )"
                ),
                {"co": company_id},
            ).mappings().first()
        return {"count": int((row or {}).get("waiting") or 0)}
    except Exception:
        logger.exception("employees_waiting_count failed company_id=%s", company_id)
        return {"count": 0}


# ---------------------------------------------------------------------------
# HR preferred-supplier submissions (AIQ-1602 Seg 4) — HR proposes a supplier
# into an admin moderation queue; an admin approves it into public.suppliers.
# ---------------------------------------------------------------------------


class SupplierSubmissionBody(BaseModel):
    name: str
    service_category: str
    coverage_scope_type: Optional[str] = "country"
    country_code: Optional[str] = None
    city_name: Optional[str] = None
    contact_email: Optional[str] = None


@router.post("/supplier-submissions")
def create_supplier_submission(
    body: SupplierSubmissionBody,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """HR proposes a preferred supplier for the ReloPass catalog → a pending row
    for admin review. Admins are emailed (fail-soft)."""
    from ..services import hr_supplier_submissions
    from ..services.admin_notify import notify_admins_supplier_submission

    company_id = _caller_company_id(user)
    try:
        submission = hr_supplier_submissions.create(
            company_id=company_id,
            submitted_by=user.get("id"),
            name=body.name,
            service_category=body.service_category,
            coverage_scope_type=body.coverage_scope_type or "country",
            country_code=body.country_code,
            city_name=body.city_name,
            contact_email=body.contact_email,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    try:
        notify_admins_supplier_submission(
            name=submission.get("name") or body.name,
            service_category=submission.get("service_category") or body.service_category,
            city=body.city_name,
            country=body.country_code,
            company_id=company_id,
        )
    except Exception:  # noqa: BLE001 — notification must never break the submit
        logger.warning("supplier_submission: admin email failed (suppressed)")
    return submission


@router.get("/supplier-submissions")
def list_my_supplier_submissions(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    from ..services import hr_supplier_submissions

    company_id = _caller_company_id(user)
    return {"submissions": hr_supplier_submissions.list_for_company(company_id)}
