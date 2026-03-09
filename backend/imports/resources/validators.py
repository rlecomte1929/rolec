"""
Validation layer for Resources import.
Validates required fields, enums, references, and data integrity.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .schemas import (
    AUDIENCE_TYPES,
    BUDGET_TIERS,
    EVENT_TYPES,
    ImportCategory,
    ImportEvent,
    ImportResource,
    ImportSource,
    ImportTag,
    RESOURCE_TYPES,
    SOURCE_TYPES,
    STATUSES,
    TAG_GROUPS,
    TRUST_TIERS,
)


def _url_ok(url: Optional[str]) -> bool:
    if not url:
        return True
    s = str(url).strip()
    if not s:
        return True
    return bool(re.match(r"^https?://[^\s]+$", s, re.IGNORECASE))


class ValidationError(Exception):
    def __init__(self, entity_type: str, row_num: int, field: str, message: str):
        self.entity_type = entity_type
        self.row_num = row_num
        self.field = field
        self.message = message
        super().__init__(f"{entity_type} row {row_num} [{field}]: {message}")


def validate_category(c: ImportCategory) -> List[Tuple[str, str]]:
    errors: List[Tuple[str, str]] = []
    if not c.key or not c.label:
        errors.append(("key/label", "Required"))
    if c.sort_order < 0:
        errors.append(("sort_order", "Must be >= 0"))
    return errors


def validate_tag(t: ImportTag) -> List[Tuple[str, str]]:
    errors: List[Tuple[str, str]] = []
    if not t.key or not t.label:
        errors.append(("key/label", "Required"))
    if t.tag_group and t.tag_group not in TAG_GROUPS:
        errors.append(("tag_group", f"Must be one of: {sorted(TAG_GROUPS)}"))
    return errors


def validate_source(s: ImportSource) -> List[Tuple[str, str]]:
    errors: List[Tuple[str, str]] = []
    if not s.source_name:
        errors.append(("source_name", "Required"))
    if s.source_type and s.source_type not in SOURCE_TYPES:
        errors.append(("source_type", f"Must be one of: {sorted(SOURCE_TYPES)}"))
    if s.trust_tier and s.trust_tier not in TRUST_TIERS:
        errors.append(("trust_tier", f"Must be one of: {sorted(TRUST_TIERS)}"))
    if not _url_ok(s.url):
        errors.append(("url", "Invalid URL format"))
    return errors


def validate_resource(
    r: ImportResource,
    category_keys: Set[str],
    tag_keys: Set[str],
    mode: str,
    allow_published: bool,
) -> List[Tuple[str, str]]:
    errors: List[Tuple[str, str]] = []
    if not r.country_code or not r.category_key or not r.title:
        errors.append(("country_code/category_key/title", "Required"))
    if r.category_key and r.category_key not in category_keys:
        errors.append(("category_key", f"Category '{r.category_key}' not found in import or DB"))
    if r.resource_type and r.resource_type not in RESOURCE_TYPES:
        errors.append(("resource_type", f"Must be one of: {sorted(RESOURCE_TYPES)}"))
    if r.audience_type and r.audience_type not in AUDIENCE_TYPES:
        errors.append(("audience_type", f"Must be one of: {sorted(AUDIENCE_TYPES)}"))
    if r.budget_tier and r.budget_tier not in BUDGET_TIERS:
        errors.append(("budget_tier", f"Must be one of: {sorted(BUDGET_TIERS)}"))
    if r.trust_tier and r.trust_tier not in TRUST_TIERS:
        errors.append(("trust_tier", f"Must be one of: {sorted(TRUST_TIERS)}"))
    if r.status and r.status not in STATUSES:
        errors.append(("status", f"Must be one of: {sorted(STATUSES)}"))
    if r.min_child_age is not None and r.max_child_age is not None and r.min_child_age > r.max_child_age:
        errors.append(("min_child_age/max_child_age", "min must be <= max"))
    if r.latitude is not None and (r.latitude < -90 or r.latitude > 90):
        errors.append(("latitude", "Must be -90 to 90"))
    if r.longitude is not None and (r.longitude < -180 or r.longitude > 180):
        errors.append(("longitude", "Must be -180 to 180"))
    if not _url_ok(r.external_url):
        errors.append(("external_url", "Invalid URL format"))
    if not _url_ok(r.booking_url):
        errors.append(("booking_url", "Invalid URL format"))
    if r.status == "published" and not allow_published:
        errors.append(("status", "Published import not allowed in current mode"))
    for tag in (r.tags or []):
        if tag and tag not in tag_keys:
            errors.append(("tags", f"Tag '{tag}' not found in import or DB"))
    return errors


def validate_event(
    e: ImportEvent,
    tag_keys: Set[str],
    mode: str,
    allow_published: bool,
) -> List[Tuple[str, str]]:
    errors: List[Tuple[str, str]] = []
    if not e.country_code or not e.city_name or not e.title or not e.start_datetime or not e.event_type:
        errors.append(("required", "country_code, city_name, title, start_datetime, event_type required"))
    if e.event_type and e.event_type not in EVENT_TYPES:
        errors.append(("event_type", f"Must be one of: {sorted(EVENT_TYPES)}"))
    if e.trust_tier and e.trust_tier not in TRUST_TIERS:
        errors.append(("trust_tier", f"Must be one of: {sorted(TRUST_TIERS)}"))
    if e.status and e.status not in STATUSES:
        errors.append(("status", f"Must be one of: {sorted(STATUSES)}"))
    if e.min_age is not None and e.max_age is not None and e.min_age > e.max_age:
        errors.append(("min_age/max_age", "min must be <= max"))
    if e.end_datetime and e.start_datetime and e.end_datetime < e.start_datetime:
        errors.append(("end_datetime", "Must be >= start_datetime"))
    if not _url_ok(e.external_url):
        errors.append(("external_url", "Invalid URL format"))
    if not _url_ok(e.booking_url):
        errors.append(("booking_url", "Invalid URL format"))
    if e.status == "published" and not allow_published:
        errors.append(("status", "Published import not allowed in current mode"))
    for tag in (e.tags or []):
        if tag and tag not in tag_keys:
            errors.append(("tags", f"Tag '{tag}' not found in import or DB"))
    return errors


def validate_bundle(
    bundle: Any,
    existing_category_keys: Set[str],
    existing_tag_keys: Set[str],
    mode: str = "draft_only",
    allow_published: bool = False,
) -> List[Dict[str, Any]]:
    """
    Validate entire bundle. Returns list of error dicts.
    existing_*_keys: keys already in DB or from earlier in same import.
    """
    errors: List[Dict[str, Any]] = []
    cat_keys = existing_category_keys | {c.key for c in bundle.categories}
    tag_keys = existing_tag_keys | {t.key for t in bundle.tags}

    for c in bundle.categories:
        for field, msg in validate_category(c):
            errors.append({"entity_type": "category", "row_num": c.row_num, "field": field, "message": msg})
    for t in bundle.tags:
        for field, msg in validate_tag(t):
            errors.append({"entity_type": "tag", "row_num": t.row_num, "field": field, "message": msg})
    for s in bundle.sources:
        for field, msg in validate_source(s):
            errors.append({"entity_type": "source", "row_num": s.row_num, "field": field, "message": msg})
    for r in bundle.resources:
        for field, msg in validate_resource(r, cat_keys, tag_keys, mode, allow_published):
            errors.append({"entity_type": "resource", "row_num": r.row_num, "field": field, "message": msg})
    for e in bundle.events:
        for field, msg in validate_event(e, tag_keys, mode, allow_published):
            errors.append({"entity_type": "event", "row_num": e.row_num, "field": field, "message": msg})

    return errors
