"""
Relocation Knowledge Graph (RKG) - Structured resources service.
Supports getResourceContext, getCountryResources, getCountryEvents, getRecommendedResources.
Queries new RKG tables; falls back to country_resources defaults when DB empty.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .country_resources import build_profile_context as _build_profile_context
from .country_resources import get_default_section_content
from .country_resources import get_personalization_hints
from .country_resources import RESOURCE_SECTIONS
from .country_resources import SECTION_LABELS


def _get_supabase():
    from .supabase_client import get_supabase_admin_client
    return get_supabase_admin_client()


def _country_code_from_name(name: str) -> str:
    mapping = {
        "norway": "NO", "singapore": "SG", "united states": "US", "usa": "US",
        "united kingdom": "UK", "uk": "UK", "germany": "DE",
    }
    return mapping.get((name or "").lower().strip(), (name or "")[:2].upper() if name else "")


def get_resource_context(draft: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive ResourceContext from case profile for personalization.
    Maps to spec: countryCode, cityName, familyType, hasChildren, childAges, etc.
    """
    profile = _build_profile_context(draft)
    cc = profile.get("country_code") or ""
    city = profile.get("destination_city") or ""
    family_status = profile.get("family_status") or "single"
    if family_status not in ("single", "couple", "family"):
        family_status = "family" if profile.get("has_children") else ("couple" if profile.get("has_spouse") else "single")
    has_children = profile.get("has_children", False)
    child_ages = profile.get("children_ages") or []
    spouse_working = profile.get("spouse_working")
    reloc_type = profile.get("relocation_type") or "permanent"
    pref_lang = profile.get("preferred_language")

    recommended_tags: List[str] = []
    if has_children:
        recommended_tags.extend(["schools", "childcare", "parks", "family_activity", "family_friendly"])
    if family_status == "single" or (not has_children and not profile.get("has_spouse")):
        recommended_tags.extend(["networking", "expat_groups", "coworking", "cinema", "concerts"])
    if profile.get("has_spouse") and spouse_working is False:
        recommended_tags.extend(["language_classes", "community", "spouse_support", "job_search"])
    if reloc_type == "short_term":
        recommended_tags.extend(["temporary_housing", "public_transport", "quick_setup"])
    if reloc_type in ("long_term", "permanent"):
        recommended_tags.extend(["registration", "schooling", "healthcare", "bank_account", "neighborhood"])

    return {
        "countryCode": cc,
        "cityName": city or None,
        "familyType": family_status,
        "hasChildren": has_children,
        "childAges": child_ages,
        "spouseWorking": spouse_working,
        "relocationType": reloc_type,
        "preferredLanguage": pref_lang,
        "recommendedTags": list(dict.fromkeys(recommended_tags)),
        "profile": profile,
    }


def get_country_resources(
    country_code: str,
    city: Optional[str] = None,
    category: Optional[str] = None,
    audience: Optional[str] = None,
    child_age_min: Optional[int] = None,
    child_age_max: Optional[int] = None,
    budget: Optional[str] = None,
    language: Optional[str] = None,
    tags: Optional[List[str]] = None,
    family_friendly: Optional[bool] = None,
    featured: Optional[bool] = None,
    published_only: bool = False,
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch resources from country_resources table with filters.
    When published_only=True (public API), only returns status=published and is_visible_to_end_users=true.
    """
    try:
        supabase = _get_supabase()
        q = (
            supabase.table("country_resources")
            .select("*")
            .eq("country_code", country_code.upper())
            .eq("is_active", True)
        )
        if published_only:
            q = q.eq("status", "published").eq("is_visible_to_end_users", True)
        elif status_filter:
            q = q.eq("status", status_filter)
        r = q.execute()
        rows = r.data or []
        if published_only and rows:
            rows = [x for x in rows if x.get("status") == "published" and x.get("is_visible_to_end_users")]

        # Filter in Python for flexibility (city: match or country-level)
        if city:
            rows = [x for x in rows if (x.get("city_name") or "").lower() == city.lower() or not x.get("city_name")]
        if category:
            cat_q = supabase.table("resource_categories").select("id").eq("key", category).limit(1).execute()
            if cat_q.data:
                cid = cat_q.data[0]["id"]
                rows = [x for x in rows if x.get("category_id") == cid]
        if audience:
            rows = [x for x in rows if x.get("audience_type") in (audience, "all")]
        if budget:
            rows = [x for x in rows if x.get("budget_tier") == budget]
        if language:
            rows = [x for x in rows if (x.get("language_code") or "").lower() == language.lower() or not x.get("language_code")]
        if family_friendly is True:
            rows = [x for x in rows if x.get("is_family_friendly")]
        if featured is True:
            rows = [x for x in rows if x.get("is_featured")]
        if child_age_min is not None:
            rows = [x for x in rows if x.get("max_child_age") is None or x.get("max_child_age", 0) >= child_age_min]
        if child_age_max is not None:
            rows = [x for x in rows if x.get("min_child_age") is None or x.get("min_child_age", 99) <= child_age_max]

        if tags:
            tag_ids_q = supabase.table("resource_tags").select("id").in_("key", tags).execute()
            tag_ids = [t["id"] for t in (tag_ids_q.data or [])]
            if tag_ids:
                rt_q = supabase.table("country_resource_tags").select("resource_id").in_("tag_id", tag_ids).execute()
                keep_ids = {x["resource_id"] for x in (rt_q.data or [])}
                rows = [x for x in rows if x.get("id") in keep_ids]
        return rows
    except Exception:
        return []


def get_country_events(
    country_code: str,
    city: Optional[str] = None,
    event_type: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    is_free: Optional[bool] = None,
    family_friendly: Optional[bool] = None,
    limit: int = 50,
    published_only: bool = False,
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch events from rkg_country_events with filters.
    When published_only=True (public API), only returns status=published and is_visible_to_end_users=true.
    """
    try:
        supabase = _get_supabase()
        q = (
            supabase.table("rkg_country_events")
            .select("*")
            .eq("country_code", country_code.upper())
            .gte("start_datetime", (date_from or datetime.now(timezone.utc)).isoformat())
            .order("start_datetime", desc=False)
            .limit(limit)
        )
        if published_only:
            q = q.eq("status", "published").eq("is_visible_to_end_users", True)
        elif status_filter:
            q = q.eq("status", status_filter)
        if city:
            q = q.eq("city_name", city)
        if event_type:
            q = q.eq("event_type", event_type)
        if date_to:
            q = q.lte("start_datetime", date_to.isoformat())
        if is_free is True:
            q = q.eq("is_free", True)
        if family_friendly is True:
            q = q.eq("is_family_friendly", True)

        r = q.execute()
        rows = r.data or []
        if published_only and rows:
            rows = [x for x in rows if x.get("status") == "published" and x.get("is_visible_to_end_users")]
        return rows
    except Exception:
        return []


def get_recommended_resources(
    context: Dict[str, Any],
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Return prioritized resources for hero / top sections."""
    cc = context.get("countryCode") or ""
    city = context.get("cityName")
    family_type = context.get("familyType", "single")
    has_children = context.get("hasChildren", False)
    tags = context.get("recommendedTags", [])

    resources = get_country_resources(
        country_code=cc,
        city=city,
        audience=family_type if family_type != "single" else None,
        family_friendly=has_children,
        featured=True,
        published_only=True,
    )
    if len(resources) < limit:
        more = get_country_resources(
            country_code=cc,
            city=city,
            featured=None,
            family_friendly=has_children if has_children else None,
            published_only=True,
        )
        seen = {r["id"] for r in resources}
        for m in more:
            if m["id"] not in seen and len(resources) < limit:
                resources.append(m)
                seen.add(m["id"])
    return resources[:limit]


def get_categories() -> List[Dict[str, Any]]:
    """Fetch active resource categories."""
    try:
        supabase = _get_supabase()
        r = supabase.table("resource_categories").select("*").eq("is_active", True).order("sort_order").execute()
        return r.data or []
    except Exception:
        return []


def resources_to_sections(
    country_code: str,
    city: str,
    resources: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Convert country_resources rows + fallback defaults into sections format
    compatible with existing frontend.
    """
    categories_list = get_categories()
    categories_by_id = {c["id"]: c for c in categories_list}
    by_category: Dict[str, List[Dict]] = {}
    for r in resources:
        cid = r.get("category_id")
        cat = categories_by_id.get(cid) if cid else None
        key = cat.get("key") if cat else "daily_life"
        if key not in by_category:
            by_category[key] = []
        by_category[key].append(r)

    sections = []
    for key in RESOURCE_SECTIONS:
        title = SECTION_LABELS.get(key, key.replace("_", " ").title())
        items = by_category.get(key, [])
        default_content = get_default_section_content(country_code, city, key)
        content: Dict[str, Any] = {"overview": default_content.get("overview", ""), "items": []}
        for it in items:
            content["items"].append({
                "id": it.get("id"),
                "title": it.get("title"),
                "summary": it.get("summary"),
                "resource_type": it.get("resource_type"),
                "external_url": it.get("external_url"),
                "booking_url": it.get("booking_url"),
                "address": it.get("address"),
                "price_range_text": it.get("price_range_text"),
                "is_family_friendly": it.get("is_family_friendly"),
                "trust_tier": it.get("trust_tier"),
            })
        if key == "admin_essentials" and default_content.get("topics"):
            content["topics"] = default_content["topics"]
        if key in ("housing", "daily_life", "community") and default_content.get("platforms"):
            content["platforms"] = default_content.get("platforms", [])
        if key == "schools" and default_content.get("school_types"):
            content["school_types"] = default_content["school_types"]
        if key == "cost_of_living" and default_content.get("items"):
            content["items"] = default_content["items"]
        if key == "safety":
            content["emergency"] = default_content.get("emergency")
            content["tips"] = default_content.get("tips", [])
        sections.append({"key": key, "title": title, "content": content})
    return sections
