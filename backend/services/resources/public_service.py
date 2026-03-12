"""
Public resources service: orchestrates public repo + context + personalization.
Uses ONLY published views. Never exposes internal governance fields.
Falls back to RKG country_resources, then curated defaults when published view is empty.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid
from typing import Any, Dict, List, Optional

from . import dto
from .context_service import build_resource_context_from_draft, score_resource_for_context
from .public_repository import (
    find_published_resources,
    find_published_resources_by_ids,
    find_published_events,
    find_active_categories,
    find_tags,
)


def get_resource_context(case_id: str, draft: Dict[str, Any]) -> Dict[str, Any]:
    """Build resource context from case draft."""
    return build_resource_context_from_draft(case_id, draft)


def get_published_resources(
    country_code: str,
    filters: Optional[Dict[str, Any]] = None,
    page: int = 1,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Fetch published resources with filters. Returns safe DTOs."""
    f = filters or {}
    child_age = f.get("childAge", "")
    child_min = child_max = None
    if isinstance(child_age, str) and "-" in child_age:
        try:
            a, b = child_age.split("-", 1)
            child_min = int(a.strip())
            child_max = int(b.strip())
        except (ValueError, TypeError):
            pass
    ff = f.get("familyFriendly")
    if isinstance(ff, str):
        ff = ff.lower() in ("true", "1", "yes") if ff else None

    rows = find_published_resources(
        country_code=country_code,
        city=f.get("city"),
        category_key=f.get("category"),
        category_id=f.get("categoryId"),
        audience_type=f.get("audienceType") or f.get("familyType"),
        child_age_min=child_min or f.get("childAgeMin"),
        child_age_max=child_max or f.get("childAgeMax"),
        budget_tier=f.get("budgetTier"),
        language=f.get("language"),
        tags=f.get("tags"),
        family_friendly=ff,
        featured=f.get("featured"),
        search=f.get("search"),
        page=page,
        limit=limit,
    )
    return [dto._to_public_resource(r) for r in rows]


def get_published_events(
    country_code: str,
    filters: Optional[Dict[str, Any]] = None,
    page: int = 1,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Fetch published events with filters. Returns safe DTOs."""
    f = filters or {}
    now = datetime.now(timezone.utc)
    days = int(f.get("daysAhead", 14))
    date_from = now
    date_to = now + timedelta(days=days)
    ff = f.get("familyFriendly")
    if isinstance(ff, str):
        ff = ff.lower() in ("true", "1", "yes") if ff else None

    rows = find_published_events(
        country_code=country_code,
        city=f.get("city"),
        event_type=f.get("eventType"),
        date_from=date_from,
        date_to=date_to,
        is_free=f.get("isFree"),
        family_friendly=ff,
        language=f.get("language"),
        tags=f.get("tags"),
        weekend_only=bool(f.get("weekendOnly")),
        upcoming_only=bool(f.get("upcomingOnly", True)),
        page=page,
        limit=limit,
    )
    return [dto._to_public_event(r) for r in rows]


def get_recommended_resources(
    context: Dict[str, Any],
    limit: int = 10,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Return prioritized resources for context.
    Groups: recommended_for_you, first_steps, family_essentials, this_weekend.
    """
    cc = context.get("countryCode") or ""
    city = context.get("cityName")
    if not cc:
        return {"recommendedForYou": [], "firstSteps": [], "familyEssentials": [], "thisWeekend": []}

    rows = find_published_resources(
        country_code=cc,
        city=city,
        family_friendly=context.get("hasChildren"),
        featured=True,
        limit=100,
    )
    rows += find_published_resources(
        country_code=cc,
        city=city,
        featured=None,
        family_friendly=context.get("hasChildren") if context.get("hasChildren") else None,
        limit=100,
    )
    seen = set()
    unique = []
    for r in rows:
        if r.get("id") and r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)

    scored = [(r, score_resource_for_context(r, context)) for r in unique if score_resource_for_context(r, context) >= 0]
    scored.sort(key=lambda x: -x[1])
    top = [r for r, _ in scored[:limit * 2]]
    dto_list = [dto._to_public_resource(r) for r in top[:limit]]

    reloc_type = context.get("relocationType", "permanent")
    has_children = context.get("hasChildren", False)
    family_essentials = [x for x in dto_list if has_children and x.get("resourceType") in ("school", "guide")][:5]
    first_steps = [x for x in dto_list if reloc_type == "short_term" or x.get("resourceType") in ("checklist_item", "official_link")][:5]

    return {
        "recommendedForYou": dto_list[:limit],
        "firstSteps": first_steps[:5],
        "familyEssentials": family_essentials,
        "thisWeekend": [],  # Events would go here; could merge with events
    }


def _merge_context_into_filters(
    context: Dict[str, Any],
    user_filters: Dict[str, Any],
) -> Dict[str, Any]:
    """When user has not set a filter, pre-fill from context so results match user requirements."""
    effective = dict(user_filters) if user_filters else {}
    if not effective.get("city") and context.get("cityName"):
        effective["city"] = context["cityName"]
    if not effective.get("audienceType") and not effective.get("familyType") and context.get("familyType"):
        effective["audienceType"] = context["familyType"]
    if effective.get("familyFriendly") is None and context.get("hasChildren"):
        effective["familyFriendly"] = True
    if not effective.get("childAge") and context.get("childAges"):
        ages = context["childAges"]
        if ages:
            effective["childAge"] = f"{min(ages)}-{max(ages)}"
    return effective


def _get_rkg_resources(
    country_code: str,
    filters: Dict[str, Any],
    context: Dict[str, Any],
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Fallback: fetch from RKG country_resources when published view is empty."""
    try:
        from ..rkg_resources import get_country_resources
        ff = filters.get("familyFriendly")
        if isinstance(ff, str):
            ff = ff.lower() in ("true", "1", "yes") if ff else None
        child_age = filters.get("childAge", "")
        child_min = child_max = None
        if isinstance(child_age, str) and "-" in child_age:
            try:
                a, b = child_age.split("-", 1)
                child_min = int(a.strip())
                child_max = int(b.strip())
            except (ValueError, TypeError):
                pass
        rows = get_country_resources(
            country_code=country_code,
            city=filters.get("city"),
            category=filters.get("category"),
            audience=filters.get("audienceType") or filters.get("familyType"),
            child_age_min=child_min,
            child_age_max=child_max,
            budget=filters.get("budgetTier"),
            language=filters.get("language"),
            family_friendly=ff,
            published_only=True,
        )
        return [dto._to_public_resource(r) for r in rows[:limit]]
    except Exception:
        return []


def _get_curated_resources_as_public(
    country_code: str,
    city: str,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Convert curated default section content into PublicResource format when DB is empty."""
    from ..country_resources import (
        RESOURCE_SECTIONS,
        SECTION_LABELS,
        get_default_section_content,
    )
    synthetic_categories = [
        {"id": f"curated_{k}", "key": k, "label": SECTION_LABELS.get(k, k.replace("_", " ").title())}
        for k in RESOURCE_SECTIONS
    ]
    categories = [dto._to_public_category(c) for c in synthetic_categories]
    cat_key_to_id = {c["key"]: c["id"] for c in synthetic_categories}

    resources: List[Dict[str, Any]] = []
    for section_key in RESOURCE_SECTIONS:
        content = get_default_section_content(country_code, city, section_key)
        cat_id = cat_key_to_id.get(section_key)

        for item in content.get("platforms", []) or []:
            resources.append({
                "id": f"curated_{uuid.uuid4().hex[:12]}",
                "countryCode": country_code,
                "cityName": city or None,
                "categoryId": cat_id,
                "title": item.get("title", ""),
                "summary": item.get("description", "") or "",
                "resourceType": "official_link",
                "isFamilyFriendly": False,
                "isFeatured": False,
                "externalUrl": item.get("url"),
                "trustTier": "curated",
            })
        for item in content.get("topics", []) or []:
            resources.append({
                "id": f"curated_{uuid.uuid4().hex[:12]}",
                "countryCode": country_code,
                "cityName": city or None,
                "categoryId": cat_id,
                "title": item.get("title", ""),
                "summary": item.get("timeline", "") or "",
                "resourceType": "checklist_item",
                "isFamilyFriendly": False,
                "isFeatured": False,
                "externalUrl": item.get("link"),
                "trustTier": "curated",
            })
        for item in content.get("groups", []) or []:
            resources.append({
                "id": f"curated_{uuid.uuid4().hex[:12]}",
                "countryCode": country_code,
                "cityName": city or None,
                "categoryId": cat_id,
                "title": item.get("title", ""),
                "summary": item.get("description", "") or "",
                "resourceType": "place",
                "isFamilyFriendly": False,
                "isFeatured": False,
                "externalUrl": item.get("url"),
                "trustTier": "curated",
            })
        for item in content.get("items", []) or []:
            if isinstance(item, dict):
                resources.append({
                    "id": f"curated_{uuid.uuid4().hex[:12]}",
                    "countryCode": country_code,
                    "cityName": city or None,
                    "categoryId": cat_id,
                    "title": item.get("title", "") or item.get("label", ""),
                    "summary": item.get("description", "") or "",
                    "resourceType": "guide",
                    "isFamilyFriendly": False,
                    "isFeatured": False,
                    "externalUrl": item.get("url"),
                    "trustTier": "curated",
                })
    return resources, categories


def get_resources_page_data(
    case_id: str,
    draft: Dict[str, Any],
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Composite endpoint: context, categories, filtered resources, events, recommended.
    Uses published views first; falls back to RKG country_resources then curated defaults.
    Applies context-derived filters so results match user requirements by default.
    """
    context = get_resource_context(case_id, draft)
    cc = context.get("countryCode") or "NO"
    city = context.get("cityName")

    effective_filters = _merge_context_into_filters(context, filters or {})
    user_filters = filters or {}

    categories = [dto._to_public_category(c) for c in find_active_categories()]
    resources = get_published_resources(cc, effective_filters, page=1, limit=50)

    if not resources:
        resources = _get_rkg_resources(cc, effective_filters, context, limit=50)
    if not resources:
        curated_resources, curated_categories = _get_curated_resources_as_public(cc, city or "")
        resources = curated_resources
        if curated_categories:
            categories = curated_categories

    events = get_published_events(cc, effective_filters, page=1, limit=20)
    if not events:
        try:
            from ..rkg_resources import get_country_events
            now = datetime.now(timezone.utc)
            ev_rows = get_country_events(
                country_code=cc,
                city=city,
                date_from=now,
                date_to=now + timedelta(days=14),
                published_only=True,
                limit=20,
            )
            events = [dto._to_public_event(e) for e in ev_rows]
        except Exception:
            pass

    recommended = get_recommended_resources(context, limit=5)
    if not recommended.get("recommendedForYou") and resources:
        recommended["recommendedForYou"] = resources[:5]
        recommended["firstSteps"] = [r for r in resources if r.get("resourceType") in ("checklist_item", "official_link")][:5]
        if context.get("hasChildren"):
            recommended["familyEssentials"] = [r for r in resources if r.get("resourceType") in ("guide", "place")][:5]

    from ..country_resources import get_personalization_hints
    profile = {
        "destination_city": city,
        "country_code": cc,
        "has_children": context.get("hasChildren"),
        "family_status": context.get("familyType"),
        "has_spouse": context.get("familyType") in ("couple", "family"),
        "spouse_working": context.get("spouseWorking"),
        "relocation_type": context.get("relocationType"),
        "children_ages": context.get("childAges"),
    }
    hints = get_personalization_hints(profile)

    return {
        "context": context,
        "categories": categories,
        "resources": resources,
        "events": events,
        "recommended": recommended,
        "hints": hints,
        "filtersApplied": user_filters,
    }
