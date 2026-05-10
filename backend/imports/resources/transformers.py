"""
Transformation layer: map Import* records to DB-ready payloads.
Resolves category_id, source_id, tag_ids from keys/names.
"""
from typing import Any, Dict, List, Optional

from .schemas import ImportCategory, ImportEvent, ImportResource, ImportSource, ImportTag


def to_category_row(c: ImportCategory, user_id: str) -> Dict[str, Any]:
    return {
        "key": c.key,
        "label": c.label,
        "description": c.description,
        "icon_name": c.icon_name,
        "sort_order": c.sort_order,
        "is_active": c.is_active,
        "created_by_user_id": user_id,
        "updated_by_user_id": user_id,
    }


def to_tag_row(t: ImportTag, user_id: str) -> Dict[str, Any]:
    return {
        "key": t.key,
        "label": t.label,
        "tag_group": t.tag_group,
        "created_by_user_id": user_id,
        "updated_by_user_id": user_id,
    }


def to_source_row(s: ImportSource, user_id: str) -> Dict[str, Any]:
    return {
        "source_name": s.source_name,
        "publisher": s.publisher,
        "source_type": s.source_type,
        "url": s.url,
        "retrieved_at": s.retrieved_at,
        "content_hash": s.content_hash,
        "notes": s.notes,
        "trust_tier": s.trust_tier,
        "created_by_user_id": user_id,
        "updated_by_user_id": user_id,
    }


def to_resource_row(
    r: ImportResource,
    category_id: str,
    source_id: Optional[str],
    tag_ids: List[str],
    user_id: str,
    status: str,
    is_visible: bool,
    external_key: Optional[str],
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "country_code": r.country_code,
        "country_name": r.country_name,
        "city_name": r.city_name or "",
        "category_id": category_id,
        "title": r.title,
        "summary": r.summary or "",
        "body": r.body,
        "content_json": r.content_json or {},
        "resource_type": r.resource_type,
        "audience_type": r.audience_type,
        "min_child_age": r.min_child_age,
        "max_child_age": r.max_child_age,
        "budget_tier": r.budget_tier,
        "language_code": r.language_code,
        "is_family_friendly": r.is_family_friendly,
        "is_featured": r.is_featured,
        "address": r.address,
        "district": r.district,
        "latitude": r.latitude,
        "longitude": r.longitude,
        "price_range_text": r.price_range_text,
        "external_url": r.external_url,
        "booking_url": r.booking_url,
        "contact_info": r.contact_info,
        "opening_hours": r.opening_hours,
        "source_id": source_id,
        "trust_tier": r.trust_tier,
        "effective_from": r.effective_from,
        "effective_to": r.effective_to,
        "status": status,
        "is_visible_to_end_users": is_visible,
        "internal_notes": r.internal_notes,
        "review_notes": r.review_notes,
        "created_by_user_id": user_id,
        "updated_by_user_id": user_id,
        "version_number": 1,
        "is_active": True,
    }
    if external_key is not None:
        row["external_key"] = external_key
    return row


def to_event_row(
    e: ImportEvent,
    source_id: Optional[str],
    tag_ids: List[str],
    user_id: str,
    status: str,
    is_visible: bool,
    external_key: Optional[str],
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "country_code": e.country_code,
        "country_name": e.country_name,
        "city_name": e.city_name,
        "title": e.title,
        "description": e.description,
        "event_type": e.event_type,
        "venue_name": e.venue_name,
        "address": e.address,
        "start_datetime": e.start_datetime,
        "end_datetime": e.end_datetime,
        "price_text": e.price_text,
        "currency": e.currency,
        "is_free": e.is_free,
        "is_family_friendly": e.is_family_friendly,
        "min_age": e.min_age,
        "max_age": e.max_age,
        "language_code": e.language_code,
        "external_url": e.external_url,
        "booking_url": e.booking_url,
        "source_id": source_id,
        "trust_tier": e.trust_tier,
        "status": status,
        "is_visible_to_end_users": is_visible,
        "internal_notes": e.internal_notes,
        "review_notes": e.review_notes,
        "created_by_user_id": user_id,
        "updated_by_user_id": user_id,
        "version_number": 1,
    }
    if external_key is not None:
        row["external_key"] = external_key
    return row
