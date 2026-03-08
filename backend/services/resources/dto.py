"""Resources module DTOs. Public DTOs exclude internal governance fields."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Public DTOs - safe for HR/Employee, never include internal notes / workflow metadata


def _to_public_resource(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map DB row to safe public resource DTO. Use only with published view data."""
    return {
        "id": row.get("id"),
        "countryCode": row.get("country_code"),
        "countryName": row.get("country_name"),
        "cityName": row.get("city_name"),
        "categoryId": row.get("category_id"),
        "title": row.get("title"),
        "summary": row.get("summary") or "",
        "contentJson": row.get("content_json"),
        "body": row.get("body"),
        "resourceType": row.get("resource_type"),
        "audienceType": row.get("audience_type"),
        "minChildAge": row.get("min_child_age"),
        "maxChildAge": row.get("max_child_age"),
        "budgetTier": row.get("budget_tier"),
        "languageCode": row.get("language_code"),
        "isFamilyFriendly": bool(row.get("is_family_friendly", False)),
        "isFeatured": bool(row.get("is_featured", False)),
        "address": row.get("address"),
        "district": row.get("district"),
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "priceRangeText": row.get("price_range_text"),
        "externalUrl": row.get("external_url"),
        "bookingUrl": row.get("booking_url"),
        "contactInfo": row.get("contact_info"),
        "openingHours": row.get("opening_hours"),
        "sourceId": row.get("source_id"),
        "trustTier": row.get("trust_tier"),
        "effectiveFrom": row.get("effective_from"),
        "effectiveTo": row.get("effective_to"),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


def _to_public_event(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map DB row to safe public event DTO."""
    return {
        "id": row.get("id"),
        "countryCode": row.get("country_code"),
        "countryName": row.get("country_name"),
        "cityName": row.get("city_name"),
        "title": row.get("title"),
        "description": row.get("description"),
        "eventType": row.get("event_type"),
        "venueName": row.get("venue_name"),
        "address": row.get("address"),
        "startDatetime": row.get("start_datetime"),
        "endDatetime": row.get("end_datetime"),
        "priceText": row.get("price_text"),
        "currency": row.get("currency"),
        "isFree": bool(row.get("is_free", False)),
        "isFamilyFriendly": bool(row.get("is_family_friendly", False)),
        "minAge": row.get("min_age"),
        "maxAge": row.get("max_age"),
        "languageCode": row.get("language_code"),
        "externalUrl": row.get("external_url"),
        "bookingUrl": row.get("booking_url"),
        "sourceId": row.get("source_id"),
        "trustTier": row.get("trust_tier"),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


def _to_public_category(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "key": row.get("key"),
        "label": row.get("label"),
        "description": row.get("description"),
        "iconName": row.get("icon_name"),
        "sortOrder": row.get("sort_order"),
    }


def _to_public_tag(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "key": row.get("key"),
        "label": row.get("label"),
        "tagGroup": row.get("tag_group"),
    }


# Type aliases for clarity
PublicResourceDto = Dict[str, Any]  # output of _to_public_resource
PublicEventDto = Dict[str, Any]  # output of _to_public_event
PublicCategoryDto = Dict[str, Any]
PublicTagDto = Dict[str, Any]


def resource_context_dto(
    case_id: str,
    country_code: str,
    country_name: Optional[str],
    city_name: Optional[str],
    family_type: str,
    has_children: bool,
    child_ages: List[int],
    spouse_working: Optional[bool],
    relocation_type: Optional[str],
    preferred_language: Optional[str],
    recommended_tags: List[str],
) -> Dict[str, Any]:
    return {
        "caseId": case_id,
        "countryCode": country_code,
        "countryName": country_name,
        "cityName": city_name,
        "familyType": family_type,
        "hasChildren": has_children,
        "childAges": child_ages,
        "spouseWorking": spouse_working,
        "relocationType": relocation_type,
        "preferredLanguage": preferred_language,
        "recommendedTags": recommended_tags,
    }


ResourceContextDto = Dict[str, Any]
ResourcesPagePayload = Dict[str, Any]
