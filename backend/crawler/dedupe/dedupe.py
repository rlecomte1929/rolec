"""
Deduplication checks for staged candidates.
Marks duplicates; does not delete.
"""
import logging
import re
from typing import Optional, Tuple

log = logging.getLogger(__name__)

# [CRAWL-QUALITY-2] Semantic overlap vs LIVE resources. The title-based
# check_resource_duplicate misses same-content-different-title overlaps (e.g. the
# LLM "Understanding Rental Costs in Germany" duplicating the hand-seeded "How the
# rental market works"). We add a cheap term-overlap signal so those get FLAGGED
# (duplicate_of_live_resource_id), not published as near-duplicates. Flag-only —
# the admin still decides; no auto-reject.
# Overlap coefficient of significant tokens. Tuned on the real 2026-06-17 case:
# "Understanding Rental Costs" vs hand-seeded "How the rental market works" scores
# ~0.22 (FLAG), while distinct same-category topics ("Navigating Rental Agreements"
# ~0.13, "Preparing for Your Move" 0.0) stay below. Flag-only, so a slight lean
# toward flagging is acceptable (the admin dismisses false positives).
SEMANTIC_DUP_THRESHOLD = 0.18

_STOPWORDS = frozenset(
    """a an and are as at be been but by can for from has have how in into is it its may
    most not of on or other that the their them then there these they this to up was were
    what when which will with you your also each only some such than where while who within""".split()
)


def _significant_tokens(text: str) -> set:
    """Lower-cased word tokens >=4 chars (incl. German/French accents), minus
    common stopwords — the distinctive terms that signal topical overlap."""
    toks = re.findall(r"[a-zàâäéèêëïîôöùûüçñ]+", (text or "").lower())
    return {t for t in toks if len(t) >= 4 and t not in _STOPWORDS}


def _resource_similarity(title_a: str, body_a: str, title_b: str, body_b: str) -> float:
    """Overlap coefficient (containment) of significant token sets — robust to the
    candidate and live resource having different lengths. 0.0-1.0."""
    a = _significant_tokens(f"{title_a} {body_a}")
    b = _significant_tokens(f"{title_b} {body_b}")
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _get_supabase():
    # Canonical client path is backend.app.services.supabase_client; the old
    # backend.services / ...services paths resolve to backend.services (nonexistent)
    # → ModuleNotFoundError, which broke duplicate checks during crawls. (CRAWL-RUN-1)
    from backend.app.services.supabase_client import get_supabase_admin_client
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


def find_live_semantic_duplicate(
    country_code: str,
    city_name: Optional[str],
    title: str,
    body: Optional[str],
) -> Optional[str]:
    """
    [CRAWL-QUALITY-2] Return the id of a published country_resources row this
    candidate semantically overlaps (same country + city, similar title+body) even
    when the TITLE differs — the gap check_resource_duplicate (title-only) misses.

    Flag-only: callers set the candidate's duplicate_of_live_resource_id so the
    admin sees the overlap; nothing is auto-rejected. Returns None on no strong
    overlap or on any query error (best-effort, never breaks the crawl).
    """
    if not (body or title):
        return None
    city = city_name or ""
    try:
        r = (
            _get_supabase()
            .table("country_resources")
            .select("id, title, summary, body")
            .eq("country_code", country_code)
            .eq("city_name", city)
            .eq("status", "published")
            .eq("is_active", True)
            .limit(100)
            .execute()
        )
    except Exception as e:  # noqa: BLE001 — best-effort
        log.debug("find_live_semantic_duplicate query failed: %s", e)
        return None

    best_id: Optional[str] = None
    best_sim = 0.0
    for row in (r.data or []):
        live_body = f"{row.get('summary', '')} {row.get('body', '')}"
        sim = _resource_similarity(title or "", body or "", row.get("title", ""), live_body)
        if sim > best_sim:
            best_sim, best_id = sim, row.get("id")
    return best_id if best_sim >= SEMANTIC_DUP_THRESHOLD else None


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
