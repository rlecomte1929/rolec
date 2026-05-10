"""
Deduplication checks for staged candidates.
Marks duplicates; does not delete.
"""
import logging
from typing import Optional, Tuple

log = logging.getLogger(__name__)


def _get_supabase():
    try:
        from backend.services.supabase_client import get_supabase_admin_client
        return get_supabase_admin_client()
    except ImportError:
        from ...services.supabase_client import get_supabase_admin_client
        return get_supabase_admin_client()


def _normalize_title(title: str) -> str:
    return " ".join((title or "").lower().split())[:200]


def check_resource_duplicate(
    country_code: str,
    city_name: Optional[str],
    title: str,
    source_url: str,
) -> Tuple[bool, Optional[str]]:
    """
    Check if resource candidate duplicates existing staged or live.
    Returns (is_duplicate, duplicate_id).
    """
    supabase = _get_supabase()
    norm_title = _normalize_title(title)
    city = city_name or ""

    # Check staged_resource_candidates (same run or prior)
    r = (
        supabase.table("staged_resource_candidates")
        .select("id, title")
        .eq("country_code", country_code)
        .eq("city_name", city)
        .in_("status", ["new", "needs_review"])
        .limit(50)
        .execute()
    )
    for row in (r.data or []):
        if _normalize_title(row.get("title", "")) == norm_title:
            return True, row.get("id")

    # Check country_resources (live)
    r2 = (
        supabase.table("country_resources")
        .select("id, title")
        .eq("country_code", country_code)
        .eq("city_name", city)
        .limit(50)
        .execute()
    )
    for row in (r2.data or []):
        if _normalize_title(row.get("title", "")) == norm_title:
            return True, row.get("id")

    return False, None


def check_event_duplicate(
    country_code: str,
    city_name: str,
    title: str,
    start_datetime: Optional[str],
) -> Tuple[bool, Optional[str]]:
    """Check if event candidate duplicates existing."""
    supabase = _get_supabase()
    norm_title = _normalize_title(title)

    r = (
        supabase.table("staged_event_candidates")
        .select("id, title, start_datetime")
        .eq("country_code", country_code)
        .eq("city_name", city_name)
        .in_("status", ["new", "needs_review"])
        .limit(50)
        .execute()
    )
    for row in (r.data or []):
        if _normalize_title(row.get("title", "")) == norm_title:
            if start_datetime and row.get("start_datetime"):
                if str(row["start_datetime"])[:19] == str(start_datetime)[:19]:
                    return True, row.get("id")
            elif not start_datetime and not row.get("start_datetime"):
                return True, row.get("id")

    return False, None
