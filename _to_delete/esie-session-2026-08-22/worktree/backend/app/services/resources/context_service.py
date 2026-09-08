"""
Resource context service: derives personalization context from case draft.
"""
from __future__ import annotations

from typing import Any, Dict, List


def _country_code_from_name(name: str) -> str:
    mapping = {
        "norway": "NO", "singapore": "SG", "united states": "US", "usa": "US",
        "united kingdom": "UK", "uk": "UK", "germany": "DE",
    }
    return mapping.get((name or "").lower().strip(), (name or "")[:2].upper() if name else "")


def build_resource_context_from_draft(
    case_id: str,
    draft: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Derive ResourceContext from case draft for personalization.
    Maps to: countryCode, cityName, familyType, hasChildren, childAges, recommendedTags, etc.
    """
    basics = draft.get("relocationBasics", {}) or {}
    family = draft.get("familyMembers", {}) or {}

    dest_country = basics.get("destCountry") or ""
    dest_city = basics.get("destCity") or ""
    country_code = _country_code_from_name(dest_country) or (dest_country[:2].upper() if dest_country else "")

    children = family.get("children") or []
    spouse = family.get("spouse") or {}
    has_spouse = bool(spouse.get("fullName"))
    spouse_working = spouse.get("wantsToWork") if spouse else None

    duration = basics.get("durationMonths")
    if duration is None:
        reloc_type = "permanent"
    elif duration < 12:
        reloc_type = "short_term"
    elif duration <= 24:
        reloc_type = "long_term"
    else:
        reloc_type = "permanent"

    family_status = family.get("maritalStatus") or ("family" if children else ("couple" if has_spouse else "single"))
    if family_status not in ("single", "couple", "family"):
        family_status = "family" if children else ("couple" if has_spouse else "single")

    has_children = len(children) > 0
    child_ages: List[int] = []
    for c in children or []:
        dob = (c or {}).get("dateOfBirth")
        if dob:
            try:
                from datetime import date
                d = date.fromisoformat(dob[:10])
                today = date.today()
                child_ages.append(today.year - d.year - ((today.month, today.day) < (d.month, d.day)))
            except (ValueError, TypeError):
                pass

    recommended_tags: List[str] = []
    if has_children:
        recommended_tags.extend(["schools", "childcare", "parks", "family_activity", "family_friendly"])
    if family_status == "single" or (not has_children and not has_spouse):
        recommended_tags.extend(["networking", "expat_groups", "coworking", "cinema", "concerts"])
    if has_spouse and spouse_working is False:
        recommended_tags.extend(["language_classes", "community", "spouse_support", "job_search"])
    if reloc_type == "short_term":
        recommended_tags.extend(["temporary_housing", "public_transport", "quick_setup"])
    if reloc_type in ("long_term", "permanent"):
        recommended_tags.extend(["registration", "schooling", "healthcare", "bank_account", "neighborhood"])

    return {
        "caseId": case_id,
        "countryCode": country_code,
        "countryName": dest_country or None,
        "cityName": dest_city or None,
        "familyType": family_status,
        "hasChildren": has_children,
        "childAges": list(dict.fromkeys(child_ages)),
        "spouseWorking": spouse_working,
        "relocationType": reloc_type,
        "preferredLanguage": basics.get("preferredLanguage") or None,
        "recommendedTags": list(dict.fromkeys(recommended_tags)),
    }


def score_resource_for_context(resource: Dict[str, Any], context: Dict[str, Any]) -> float:
    """Score a resource for relevance to context. Higher = better match."""
    score = 0.0
    cc = (context.get("countryCode") or "").upper()
    city = (context.get("cityName") or "").strip().lower()
    family_type = context.get("familyType", "single")
    has_children = context.get("hasChildren", False)
    child_ages = context.get("childAges") or []
    tags = set(context.get("recommendedTags") or [])

    if (resource.get("country_code") or "").upper() != cc:
        return -1.0

    if city and (resource.get("city_name") or "").strip().lower() == city:
        score += 2.0
    elif not resource.get("city_name"):
        score += 1.0

    if resource.get("audience_type") in (family_type, "all"):
        score += 0.5
    if resource.get("is_family_friendly") and has_children:
        score += 1.0
    if resource.get("is_featured"):
        score += 0.5

    min_a, max_a = resource.get("min_child_age"), resource.get("max_child_age")
    if has_children and child_ages:
        for age in child_ages:
            if (min_a is None or min_a <= age) and (max_a is None or max_a >= age):
                score += 1.0
                break

    return score


def score_event_for_context(event: Dict[str, Any], context: Dict[str, Any]) -> float:
    """Score an event for relevance to context."""
    score = 0.0
    cc = (context.get("countryCode") or "").upper()
    city = (context.get("cityName") or "").strip().lower()

    if (event.get("country_code") or "").upper() != cc:
        return -1.0
    if city and (event.get("city_name") or "").strip().lower() == city:
        score += 2.0
    elif not event.get("city_name"):
        score += 1.0
    if event.get("is_family_friendly") and context.get("hasChildren"):
        score += 1.0
    return score
