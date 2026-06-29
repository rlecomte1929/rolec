"""AIQ-1349 P2 — research_requests: controlled intake for customer-requested
immigration research on an uncovered corridor.

Flow: customer requests → row (pending) + a review-queue item → admin approves
(no charge yet; estimated_cost recorded for later invoicing) → status in_progress
for the P3 curation flow. Mirrors scrape_safety's destination-request service;
uses the Supabase admin client (RLS is defense-in-depth).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)

# Placeholder list price recorded on each request (no charge taken yet — the
# admin-approved flow records cost for later invoicing). Tune as the moat matures.
RESEARCH_REQUEST_DEFAULT_COST = 500

_OPEN_STATUSES = ("pending", "approved", "in_progress")


def _get_supabase():
    return get_supabase_admin_client()


def _corridor(origin: Optional[str], dest: str) -> str:
    o = (origin or "").strip().upper()
    d = (dest or "").strip().upper()
    return f"{o}→{d}" if o else d


def open_research_request(
    *,
    company_id: str,
    requester_user_id: str,
    dest_country: str,
    origin_country: Optional[str] = None,
    purpose: Optional[str] = None,
    scope: Optional[str] = None,
) -> Dict[str, Any]:
    """Create (or return the existing open) research request for a corridor, and
    attach a curation review-queue item."""
    sb = _get_supabase()
    corridor = _corridor(origin_country, dest_country)

    existing = (
        sb.table("research_requests")
        .select("*")
        .eq("company_id", company_id)
        .eq("corridor", corridor)
        .in_("status", list(_OPEN_STATUSES))
        .limit(1)
        .execute()
    ).data
    if existing:
        return existing[0]

    row = {
        "company_id": company_id,
        "requester_user_id": requester_user_id,
        "origin_country": (origin_country or "").strip().upper() or None,
        "dest_country": (dest_country or "").strip().upper(),
        "corridor": corridor,
        "purpose": purpose,
        "scope": scope,
        "estimated_cost": RESEARCH_REQUEST_DEFAULT_COST,
        "status": "pending",
    }
    created = (sb.table("research_requests").insert(row).execute().data or [{}])[0]

    # Attach a curation queue item (best-effort) + record its id on the request.
    try:
        from .review_queue_service import create_queue_item_from_research_request
        qi = create_queue_item_from_research_request(created)
        if qi and created.get("id"):
            sb.table("research_requests").update({"created_queue_item_id": qi.get("id")}).eq(
                "id", created["id"]
            ).execute()
            created["created_queue_item_id"] = qi.get("id")
    except Exception as e:  # noqa: BLE001
        log.warning("research request: queue-item creation failed: %s", e)

    return created


def list_research_requests(status: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    sb = _get_supabase()
    q = sb.table("research_requests").select("*").order("created_at", desc=True).limit(limit)
    if status:
        q = q.eq("status", status)
    return q.execute().data or []


def resolve_research_request(
    *, request_id: str, new_status: str, actor_user_id: str, notes: Optional[str] = None
) -> Dict[str, Any]:
    """Admin approve/reject. Approve advances to `in_progress` (curation begins in
    P3); reject closes it."""
    if new_status not in ("approved", "rejected"):
        raise ValueError("new_status must be 'approved' or 'rejected'")
    sb = _get_supabase()
    # 'approved' immediately advances to in_progress so the P3 curation owns it.
    effective = "in_progress" if new_status == "approved" else "rejected"
    patch = {
        "status": effective,
        "resolved_by": actor_user_id,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }
    if notes is not None:
        patch["notes"] = notes
    updated = (
        sb.table("research_requests").update(patch).eq("id", request_id).execute().data or [{}]
    )[0]
    return updated
