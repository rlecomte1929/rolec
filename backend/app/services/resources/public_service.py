"""
Public resources service: orchestrates public repo + context + personalization.
Uses ONLY published views. Never exposes internal governance fields.
Falls back to RKG country_resources, then curated defaults when published view is empty.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
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


def _curated_id(section_key: str, kind: str, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")[:48]
    return f"curated_{section_key}_{kind}_{slug or 'item'}"


def _curated_card(
    country_code: str,
    city: str,
    category_id: Optional[str],
    *,
    section_key: str,
    kind: str,
    title: str,
    summary: str = "",
    resource_type: str = "guide",
    url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    title = (title or "").strip()
    if not title:
        return None
    return {
        "id": _curated_id(section_key, kind, title),
        "countryCode": country_code,
        "cityName": city or None,
        "categoryId": category_id,
        "title": title,
        "summary": summary or "",
        "resourceType": resource_type,
        "isFamilyFriendly": False,
        "isFeatured": False,
        "externalUrl": url,
        "trustTier": "curated",
    }


def build_settling_guide(country_code: str, city: str) -> Dict[str, Any]:
    """Deterministic settle-in pack from curated country defaults (no LLM)."""
    from ..country_resources import get_default_section_content

    cc = (country_code or "").upper()
    welcome = get_default_section_content(cc, city, "welcome")
    admin = get_default_section_content(cc, city, "admin_essentials")
    community = get_default_section_content(cc, city, "community")
    safety = get_default_section_content(cc, city, "safety")
    first_steps: List[Dict[str, Any]] = []
    for topic in admin.get("topics") or []:
        if not isinstance(topic, dict) or not topic.get("title"):
            continue
        first_steps.append(
            {
                "title": topic.get("title"),
                "timeline": topic.get("timeline") or "",
                "url": topic.get("link"),
            }
        )
    groups: List[Dict[str, Any]] = []
    for group in community.get("groups") or []:
        if not isinstance(group, dict) or not group.get("title"):
            continue
        groups.append(
            {
                "title": group.get("title"),
                "url": group.get("url"),
                "description": group.get("description") or "",
            }
        )
    return {
        "culturalAwareness": {
            "intro": welcome.get("intro") or "",
            "tips": [t for t in (welcome.get("cultural_tips") or []) if t],
            "workCulture": [t for t in (welcome.get("work_culture") or []) if t],
        },
        "firstSteps": first_steps,
        "community": {
            "overview": community.get("overview") or "",
            "groups": groups,
        },
        "practicalTips": [t for t in (safety.get("tips") or []) if t],
        "emergency": safety.get("emergency"),
    }


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

        intro = content.get("intro")
        if intro:
            card = _curated_card(
                country_code, city, cat_id,
                section_key=section_key, kind="intro",
                title="How to approach daily life here",
                summary=str(intro),
                resource_type="guide",
            )
            if card:
                resources.append(card)
        for tip in content.get("cultural_tips") or []:
            card = _curated_card(
                country_code, city, cat_id,
                section_key=section_key, kind="tip",
                title=str(tip),
                summary="Cultural awareness",
                resource_type="guide",
            )
            if card:
                resources.append(card)
        for line in content.get("work_culture") or []:
            card = _curated_card(
                country_code, city, cat_id,
                section_key=section_key, kind="work",
                title=str(line),
                summary="How people work here",
                resource_type="guide",
            )
            if card:
                resources.append(card)
        overview = content.get("overview")
        if overview:
            card = _curated_card(
                country_code, city, cat_id,
                section_key=section_key, kind="overview",
                title=SECTION_LABELS.get(section_key, section_key.replace("_", " ").title()),
                summary=str(overview),
                resource_type="guide",
            )
            if card:
                resources.append(card)
        for item in content.get("platforms", []) or []:
            card = _curated_card(
                country_code, city, cat_id,
                section_key=section_key, kind="platform",
                title=item.get("title", ""),
                summary=item.get("description", "") or "",
                resource_type="official_link",
                url=item.get("url"),
            )
            if card:
                resources.append(card)
        for item in content.get("topics", []) or []:
            card = _curated_card(
                country_code, city, cat_id,
                section_key=section_key, kind="topic",
                title=item.get("title", ""),
                summary=item.get("timeline", "") or "",
                resource_type="checklist_item",
                url=item.get("link"),
            )
            if card:
                resources.append(card)
        for item in content.get("groups", []) or []:
            card = _curated_card(
                country_code, city, cat_id,
                section_key=section_key, kind="group",
                title=item.get("title", ""),
                summary=item.get("description", "") or "",
                resource_type="place",
                url=item.get("url"),
            )
            if card:
                resources.append(card)
        for name in content.get("neighborhoods") or []:
            card = _curated_card(
                country_code, city, cat_id,
                section_key=section_key, kind="area",
                title=str(name),
                summary="Area to know when choosing housing",
                resource_type="place",
            )
            if card:
                resources.append(card)
        for name in content.get("school_types") or []:
            card = _curated_card(
                country_code, city, cat_id,
                section_key=section_key, kind="school",
                title=str(name),
                summary="School type in this destination",
                resource_type="guide",
            )
            if card:
                resources.append(card)
        for item in content.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            value = item.get("value") or ""
            note = item.get("note") or ""
            summary = item.get("description") or ""
            if value:
                summary = f"{value}" + (f" — {summary}" if summary else "")
            if note:
                summary = f"{summary} ({note})".strip() if summary else str(note)
            card = _curated_card(
                country_code, city, cat_id,
                section_key=section_key, kind="item",
                title=item.get("title", "") or item.get("label", ""),
                summary=summary,
                resource_type="guide",
                url=item.get("url"),
            )
            if card:
                resources.append(card)
        for tip in content.get("tips") or []:
            card = _curated_card(
                country_code, city, cat_id,
                section_key=section_key, kind="safety",
                title=str(tip),
                summary="Practical tip",
                resource_type="guide",
            )
            if card:
                resources.append(card)
        emergency = content.get("emergency")
        if emergency:
            card = _curated_card(
                country_code, city, cat_id,
                section_key=section_key, kind="emergency",
                title=f"Emergency: {emergency}",
                summary="Keep this number in your phone.",
                resource_type="guide",
            )
            if card:
                resources.append(card)
    return resources, categories


def build_preview_context(
    country_code: str,
    country_name: Optional[str] = None,
    city_name: Optional[str] = None,
    family_type: str = "single",
    relocation_type: str = "permanent",
    has_children: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Build a synthetic ResourceContext for HR-side preview.

    Mirrors build_resource_context_from_draft(...) so the same scoring,
    recommended-tags, and filters apply, but inputs come from explicit
    HR-chosen knobs instead of a case draft.
    """
    cc = (country_code or "").upper().strip()
    family = (family_type or "single").lower()
    if family not in ("single", "couple", "family"):
        family = "single"
    reloc = (relocation_type or "permanent").lower()
    if reloc not in ("short_term", "long_term", "permanent"):
        reloc = "permanent"
    children = bool(has_children) if has_children is not None else (family == "family")

    recommended_tags: List[str] = []
    if children:
        recommended_tags.extend(["schools", "childcare", "parks", "family_activity", "family_friendly"])
    if family == "single":
        recommended_tags.extend(["networking", "expat_groups", "coworking", "cinema", "concerts"])
    if reloc == "short_term":
        recommended_tags.extend(["temporary_housing", "public_transport", "quick_setup"])
    if reloc in ("long_term", "permanent"):
        recommended_tags.extend(["registration", "schooling", "healthcare", "bank_account", "neighborhood"])

    return {
        "caseId": None,
        "countryCode": cc,
        "countryName": country_name or None,
        "cityName": (city_name or None) and city_name.strip() or None,
        "familyType": family,
        "hasChildren": children,
        "childAges": [],
        "spouseWorking": None,
        "relocationType": reloc,
        "preferredLanguage": None,
        "recommendedTags": list(dict.fromkeys(recommended_tags)),
        "previewMode": True,
    }


def get_resources_page_data_for_preview(
    country_code: str,
    country_name: Optional[str] = None,
    city_name: Optional[str] = None,
    family_type: str = "single",
    relocation_type: str = "permanent",
    has_children: Optional[bool] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    HR-side preview composite. Same shape as get_resources_page_data, but
    context comes from explicit HR-chosen knobs instead of a case draft.
    """
    context = build_preview_context(
        country_code=country_code,
        country_name=country_name,
        city_name=city_name,
        family_type=family_type,
        relocation_type=relocation_type,
        has_children=has_children,
    )
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
        "settlingGuide": build_settling_guide(cc, city or ""),
        "filtersApplied": user_filters,
    }


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
        "settlingGuide": build_settling_guide(cc, city or ""),
        "filtersApplied": user_filters,
    }
