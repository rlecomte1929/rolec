"""
P3-02d · Dead-link detection service.

Tracks consecutive HTTP-404 responses on source_pages. When a URL returns 404
on 3 consecutive crawl runs it is considered a dead link: the ops_notifications
table receives an alert listing every immigration_requirement that cites the URL
via its instructions_url field so the ops team knows which corridors are affected.

Design decisions:
  - 404 only: transient errors (502/503/network) are handled by the retry logic in
    P3-02a. A 404 means the official page was removed — that is the dead-link signal.
  - Counter lives on source_pages.consecutive_404_count (migration 20260609110000).
    Reset to 0 on any successful fetch so a transient 404 during an outage doesn't
    permanently flag a live URL.
  - Alerting: ops_notification_service.create_or_update_notification() is already
    wired for admin review. Slack/email delivery is added in P3-02c (#336) — a
    # TODO [P3-02c] comment marks the hook point.
  - No production rule data is modified: detection is read-only against
    immigration_requirements and writes only to source_pages + ops_notifications.

Usage (called automatically from crawler/staging/writer._sync_source_page):
    from backend.app.services.dead_link_service import update_404_counter
    new_count = update_404_counter(url, is_404=True)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)

DEAD_LINK_THRESHOLD = 3  # consecutive 404s before a URL is flagged as dead


def _get_supabase():
    return get_supabase_admin_client()


# ---------------------------------------------------------------------------
# Counter management
# ---------------------------------------------------------------------------

def update_404_counter(url: str, is_404: bool) -> int:
    """
    Increment or reset the consecutive_404_count on source_pages for *url*.

    Returns the NEW counter value. If the row does not exist yet (first crawl),
    returns 0 for a successful fetch or 1 for a 404.

    Callers should trigger handle_dead_link(url) when the returned count reaches
    DEAD_LINK_THRESHOLD.
    """
    supabase = _get_supabase()
    try:
        rows = (
            supabase.table("source_pages")
            .select("id, consecutive_404_count")
            .eq("url", url)
            .limit(1)
            .execute()
        ).data or []

        if not rows:
            # Row doesn't exist yet — will be created by _sync_source_page shortly.
            return 1 if is_404 else 0

        row_id = rows[0]["id"]
        current_count: int = rows[0].get("consecutive_404_count") or 0

        if is_404:
            new_count = current_count + 1
        else:
            new_count = 0

        supabase.table("source_pages").update(
            {"consecutive_404_count": new_count}
        ).eq("id", row_id).execute()

        return new_count

    except Exception:
        log.exception("dead_link_service: could not update 404 counter for %s", url)
        return 0


# ---------------------------------------------------------------------------
# Citing-requirement lookup
# ---------------------------------------------------------------------------

def find_citing_immigration_requirements(url: str) -> List[Dict[str, Any]]:
    """
    Return immigration_requirements rows whose instructions_url matches *url*.
    Used to report which corridors / document types reference a dead link.
    """
    supabase = _get_supabase()
    try:
        result = (
            supabase.table("immigration_requirements")
            .select(
                "id, corridor_from, corridor_to, visa_type, employee_type, "
                "document_type, document_name, instructions_url"
            )
            .eq("instructions_url", url)
            .execute()
        )
        return result.data or []
    except Exception:
        log.exception("dead_link_service: could not query citing requirements for %s", url)
        return []


# ---------------------------------------------------------------------------
# Dead-link handling (threshold reached)
# ---------------------------------------------------------------------------

def handle_dead_link(url: str) -> None:
    """
    Called when consecutive_404_count reaches DEAD_LINK_THRESHOLD.

    Looks up all immigration_requirements that cite *url* and raises an
    ops_notification summarising the affected corridors. The URL's
    is_accessible flag is already set to False by the crawler before this
    function is called.

    Does NOT modify any policy / roadmap data — read-only w.r.t. rule content.
    """
    log.warning(
        "dead_link_service: %s has returned 404 %d consecutive times — flagging as dead link",
        url, DEAD_LINK_THRESHOLD,
    )

    citing = find_citing_immigration_requirements(url)

    corridors: List[str] = sorted({
        f"{r['corridor_from']}→{r['corridor_to']}"
        for r in citing
        if r.get("corridor_from") and r.get("corridor_to")
    })

    message = (
        f"Dead link detected: {url} has returned HTTP 404 on "
        f"{DEAD_LINK_THRESHOLD} consecutive crawl runs."
    )
    if corridors:
        message += f" Affecting corridors: {', '.join(corridors)}."
        message += f" {len(citing)} requirement row(s) cite this URL."
    else:
        message += " No immigration_requirements currently cite this URL."

    # Fire ops notification (admin review queue) — best-effort; never propagate.
    try:
        _raise_ops_notification(url=url, message=message, citing=citing)
    except Exception:
        log.exception("dead_link_service: notification dispatch failed for %s; continuing", url)

    # TODO [P3-02c]: once monitoring_alerts.py lands on main (#336), call:
    #   from .monitoring_alerts import send_slack_alert, send_alert_email
    #   send_slack_alert(f"🔴 Dead link: {url}\n{message}")
    #   send_alert_email(subject=f"Dead link: {url}", body=message)


def _raise_ops_notification(
    url: str,
    message: str,
    citing: List[Dict[str, Any]],
) -> None:
    """Create or re-trigger an ops_notification for the dead link."""
    try:
        from .ops_notification_service import create_or_update_notification

        affected_corridors = sorted({
            f"{r['corridor_from']}→{r['corridor_to']}"
            for r in citing
            if r.get("corridor_from") and r.get("corridor_to")
        })

        create_or_update_notification(
            notification_type="dead_link_detected",
            severity="high",
            title=f"Dead link: {url[:80]}{'…' if len(url) > 80 else ''}",
            description=message,
            metadata={
                "url": url,
                "consecutive_404_count": DEAD_LINK_THRESHOLD,
                "affected_corridors": affected_corridors,
                "affected_requirement_count": len(citing),
            },
        )
        log.info("dead_link_service: ops_notification raised for %s", url)
    except Exception:
        log.exception(
            "dead_link_service: could not raise ops_notification for dead link %s; "
            "continuing (best-effort alerting)",
            url,
        )


# ---------------------------------------------------------------------------
# Admin / query helpers
# ---------------------------------------------------------------------------

def get_dead_link_sources(threshold: int = DEAD_LINK_THRESHOLD) -> List[Dict[str, Any]]:
    """
    Return all source_pages rows where consecutive_404_count >= threshold.
    Used by the admin source-monitor dashboard (P3-02b) to highlight dead links.
    """
    supabase = _get_supabase()
    try:
        result = (
            supabase.table("source_pages")
            .select(
                "id, url, tier, http_status, is_accessible, "
                "consecutive_404_count, last_fetched_at"
            )
            .gte("consecutive_404_count", threshold)
            .order("consecutive_404_count", desc=True)
            .execute()
        )
        return result.data or []
    except Exception:
        log.exception("dead_link_service: could not query dead-link sources")
        return []
