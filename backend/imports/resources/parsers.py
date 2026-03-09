"""
CSV and JSON parsers for Resources import.
Normalizes input into typed Import* records.
"""
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .schemas import (
    ImportBundle,
    ImportCategory,
    ImportEvent,
    ImportResource,
    ImportSource,
    ImportTag,
    TAG_GROUPS,
)


# --- Helpers ---
def _trim(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    t = str(s).strip()
    return t if t else None


def _parse_bool(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("true", "yes", "1", "y"):
        return True
    if s in ("false", "no", "0", "n", ""):
        return False
    return bool(val)


def _parse_int(val: Any) -> Optional[int]:
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _parse_float(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_tags(val: Any) -> List[str]:
    """Parse tags from JSON array, comma-sep, or pipe-sep string."""
    if val is None or val == "":
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if x]
    s = str(val).strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            arr = json.loads(s)
            return [str(x).strip() for x in arr if x] if isinstance(arr, list) else []
        except json.JSONDecodeError:
            pass
    for sep in (",", "|", ";"):
        if sep in s:
            return [x.strip() for x in s.split(sep) if x.strip()]
    return [s] if s else []


def _parse_json_object(val: Any) -> Optional[Dict[str, Any]]:
    if val is None or val == "":
        return None
    if isinstance(val, dict):
        return val
    s = str(val).strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _parse_date(val: Any) -> Optional[str]:
    """Return ISO date/datetime string or None."""
    if val is None or val == "":
        return None
    s = str(val).strip()
    return s if s else None


def _row_dict(headers: List[str], values: List[str]) -> Dict[str, str]:
    out = {}
    for i, h in enumerate(headers):
        if i < len(values):
            out[h.strip().lower().replace(" ", "_")] = values[i]
    return out


# --- CSV parsers ---
def parse_csv_categories(path: Union[str, Path]) -> List[ImportCategory]:
    out: List[ImportCategory] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        headers = [h.strip().lower().replace(" ", "_") for h in next(reader, [])]
        for row_num, row in enumerate(reader, start=2):
            d = _row_dict(headers, row)
            key = _trim(d.get("key"))
            label = _trim(d.get("label"))
            if not key or not label:
                continue
            out.append(ImportCategory(
                key=key,
                label=label,
                description=_trim(d.get("description")),
                icon_name=_trim(d.get("icon_name")),
                sort_order=_parse_int(d.get("sort_order")) or 0,
                is_active=_parse_bool(d.get("is_active", True)),
                row_num=row_num,
            ))
    return out


def parse_csv_tags(path: Union[str, Path]) -> List[ImportTag]:
    out: List[ImportTag] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        headers = [h.strip().lower().replace(" ", "_") for h in next(reader, [])]
        for row_num, row in enumerate(reader, start=2):
            d = _row_dict(headers, row)
            key = _trim(d.get("key"))
            label = _trim(d.get("label"))
            if not key or not label:
                continue
            out.append(ImportTag(
                key=key,
                label=label,
                tag_group=_trim(d.get("tag_group")),
                row_num=row_num,
            ))
    return out


def parse_csv_sources(path: Union[str, Path]) -> List[ImportSource]:
    out: List[ImportSource] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        headers = [h.strip().lower().replace(" ", "_") for h in next(reader, [])]
        for row_num, row in enumerate(reader, start=2):
            d = _row_dict(headers, row)
            name = _trim(d.get("source_name"))
            if not name:
                continue
            out.append(ImportSource(
                source_name=name,
                publisher=_trim(d.get("publisher")),
                source_type=_trim(d.get("source_type")) or "community",
                url=_trim(d.get("url")),
                retrieved_at=_parse_date(d.get("retrieved_at")),
                content_hash=_trim(d.get("content_hash")),
                notes=_trim(d.get("notes")),
                trust_tier=_trim(d.get("trust_tier")) or "T2",
                row_num=row_num,
            ))
    return out


def parse_csv_resources(path: Union[str, Path]) -> List[ImportResource]:
    out: List[ImportResource] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        headers = [h.strip().lower().replace(" ", "_") for h in next(reader, [])]
        for row_num, row in enumerate(reader, start=2):
            d = _row_dict(headers, row)
            cc = _trim(d.get("country_code"))
            cat = _trim(d.get("category_key"))
            title = _trim(d.get("title"))
            if not cc or not cat or not title:
                continue
            content_json = _parse_json_object(d.get("content_json"))
            contact_info = _trim(d.get("contact_info")) or (json.dumps(content_json.get("contact_info")) if content_json and isinstance(content_json.get("contact_info"), dict) else None)
            opening_hours = _trim(d.get("opening_hours")) or (json.dumps(content_json.get("opening_hours")) if content_json and isinstance(content_json.get("opening_hours"), (dict, list)) else None)
            out.append(ImportResource(
                country_code=cc.upper(),
                country_name=_trim(d.get("country_name")),
                city_name=_trim(d.get("city_name")),
                category_key=cat,
                title=title,
                summary=_trim(d.get("summary")),
                resource_type=_trim(d.get("resource_type")) or "guide",
                audience_type=_trim(d.get("audience_type")) or "all",
                body=_trim(d.get("body")),
                content_json=content_json,
                min_child_age=_parse_int(d.get("min_child_age")),
                max_child_age=_parse_int(d.get("max_child_age")),
                budget_tier=_trim(d.get("budget_tier")),
                language_code=_trim(d.get("language_code")),
                is_family_friendly=_parse_bool(d.get("is_family_friendly")),
                is_featured=_parse_bool(d.get("is_featured")),
                address=_trim(d.get("address")),
                district=_trim(d.get("district")),
                latitude=_parse_float(d.get("latitude")),
                longitude=_parse_float(d.get("longitude")),
                price_range_text=_trim(d.get("price_range_text")),
                external_url=_trim(d.get("external_url")),
                booking_url=_trim(d.get("booking_url")),
                contact_info=contact_info,
                opening_hours=opening_hours,
                source_url=_trim(d.get("source_url")),
                source_name=_trim(d.get("source_name")),
                trust_tier=_trim(d.get("trust_tier")),
                effective_from=_parse_date(d.get("effective_from")),
                effective_to=_parse_date(d.get("effective_to")),
                tags=_parse_tags(d.get("tags")),
                status=_trim(d.get("status")) or "draft",
                is_visible_to_end_users=_parse_bool(d.get("is_visible_to_end_users")),
                internal_notes=_trim(d.get("internal_notes")),
                review_notes=_trim(d.get("review_notes")),
                external_key=_trim(d.get("external_key")),
                row_num=row_num,
            ))
    return out


def parse_csv_events(path: Union[str, Path]) -> List[ImportEvent]:
    out: List[ImportEvent] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        headers = [h.strip().lower().replace(" ", "_") for h in next(reader, [])]
        for row_num, row in enumerate(reader, start=2):
            d = _row_dict(headers, row)
            cc = _trim(d.get("country_code"))
            city = _trim(d.get("city_name"))
            title = _trim(d.get("title"))
            start = _parse_date(d.get("start_datetime"))
            event_type = _trim(d.get("event_type"))
            if not cc or not city or not title or not start or not event_type:
                continue
            out.append(ImportEvent(
                country_code=cc.upper(),
                country_name=_trim(d.get("country_name")),
                city_name=city,
                title=title,
                event_type=event_type,
                start_datetime=start,
                description=_trim(d.get("description")),
                venue_name=_trim(d.get("venue_name")),
                address=_trim(d.get("address")),
                end_datetime=_parse_date(d.get("end_datetime")),
                price_text=_trim(d.get("price_text")),
                currency=_trim(d.get("currency")),
                is_free=_parse_bool(d.get("is_free")),
                is_family_friendly=_parse_bool(d.get("is_family_friendly")),
                min_age=_parse_int(d.get("min_age")),
                max_age=_parse_int(d.get("max_age")),
                language_code=_trim(d.get("language_code")),
                external_url=_trim(d.get("external_url")),
                booking_url=_trim(d.get("booking_url")),
                source_url=_trim(d.get("source_url")),
                source_name=_trim(d.get("source_name")),
                trust_tier=_trim(d.get("trust_tier")),
                tags=_parse_tags(d.get("tags")),
                status=_trim(d.get("status")) or "draft",
                is_visible_to_end_users=_parse_bool(d.get("is_visible_to_end_users")),
                internal_notes=_trim(d.get("internal_notes")),
                review_notes=_trim(d.get("review_notes")),
                external_key=_trim(d.get("external_key")),
                row_num=row_num,
            ))
    return out


# --- JSON parsers ---
def _norm_key(s: str) -> str:
    return re.sub(r"\s+", "_", str(s).strip().lower())


def parse_json_categories(data: List[Dict[str, Any]]) -> List[ImportCategory]:
    out: List[ImportCategory] = []
    for i, d in enumerate(data):
        key = _trim(d.get("key"))
        label = _trim(d.get("label"))
        if not key or not label:
            continue
        out.append(ImportCategory(
            key=key,
            label=label,
            description=_trim(d.get("description")),
            icon_name=_trim(d.get("icon_name")),
            sort_order=_parse_int(d.get("sort_order")) or 0,
            is_active=_parse_bool(d.get("is_active", True)),
            row_num=i + 1,
        ))
    return out


def parse_json_tags(data: List[Dict[str, Any]]) -> List[ImportTag]:
    out: List[ImportTag] = []
    for i, d in enumerate(data):
        key = _trim(d.get("key"))
        label = _trim(d.get("label"))
        if not key or not label:
            continue
        out.append(ImportTag(
            key=key,
            label=label,
            tag_group=_trim(d.get("tag_group")),
            row_num=i + 1,
        ))
    return out


def parse_json_sources(data: List[Dict[str, Any]]) -> List[ImportSource]:
    out: List[ImportSource] = []
    for i, d in enumerate(data):
        name = _trim(d.get("source_name"))
        if not name:
            continue
        out.append(ImportSource(
            source_name=name,
            publisher=_trim(d.get("publisher")),
            source_type=_trim(d.get("source_type")) or "community",
            url=_trim(d.get("url")),
            retrieved_at=_parse_date(d.get("retrieved_at")),
            content_hash=_trim(d.get("content_hash")),
            notes=_trim(d.get("notes")),
            trust_tier=_trim(d.get("trust_tier")) or "T2",
            row_num=i + 1,
        ))
    return out


def parse_json_resources(data: List[Dict[str, Any]]) -> List[ImportResource]:
    out: List[ImportResource] = []
    for i, d in enumerate(data):
        cc = _trim(d.get("country_code"))
        cat = _trim(d.get("category_key"))
        title = _trim(d.get("title"))
        if not cc or not cat or not title:
            continue
        content_json = d.get("content_json")
        if isinstance(content_json, dict):
            pass
        elif content_json is not None:
            content_json = _parse_json_object(content_json) if isinstance(content_json, str) else None
        else:
            content_json = None
        tags_raw = d.get("tags", [])
        tags = tags_raw if isinstance(tags_raw, list) else _parse_tags(tags_raw)
        out.append(ImportResource(
            country_code=cc.upper(),
            country_name=_trim(d.get("country_name")),
            city_name=_trim(d.get("city_name")),
            category_key=cat,
            title=title,
            summary=_trim(d.get("summary")),
            resource_type=_trim(d.get("resource_type")) or "guide",
            audience_type=_trim(d.get("audience_type")) or "all",
            body=_trim(d.get("body")),
            content_json=content_json,
            min_child_age=_parse_int(d.get("min_child_age")),
            max_child_age=_parse_int(d.get("max_child_age")),
            budget_tier=_trim(d.get("budget_tier")),
            language_code=_trim(d.get("language_code")),
            is_family_friendly=_parse_bool(d.get("is_family_friendly")),
            is_featured=_parse_bool(d.get("is_featured")),
            address=_trim(d.get("address")),
            district=_trim(d.get("district")),
            latitude=_parse_float(d.get("latitude")),
            longitude=_parse_float(d.get("longitude")),
            price_range_text=_trim(d.get("price_range_text")),
            external_url=_trim(d.get("external_url")),
            booking_url=_trim(d.get("booking_url")),
            contact_info=_trim(d.get("contact_info")) or (json.dumps(d.get("contact_info")) if isinstance(d.get("contact_info"), (dict, list)) else None),
            opening_hours=_trim(d.get("opening_hours")) or (json.dumps(d.get("opening_hours")) if isinstance(d.get("opening_hours"), (dict, list)) else None),
            source_url=_trim(d.get("source_url")),
            source_name=_trim(d.get("source_name")),
            trust_tier=_trim(d.get("trust_tier")),
            effective_from=_parse_date(d.get("effective_from")),
            effective_to=_parse_date(d.get("effective_to")),
            tags=[str(t).strip() for t in tags if t],
            status=_trim(d.get("status")) or "draft",
            is_visible_to_end_users=_parse_bool(d.get("is_visible_to_end_users")),
            internal_notes=_trim(d.get("internal_notes")),
            review_notes=_trim(d.get("review_notes")),
            external_key=_trim(d.get("external_key")),
            row_num=i + 1,
        ))
    return out


def parse_json_events(data: List[Dict[str, Any]]) -> List[ImportEvent]:
    out: List[ImportEvent] = []
    for i, d in enumerate(data):
        cc = _trim(d.get("country_code"))
        city = _trim(d.get("city_name"))
        title = _trim(d.get("title"))
        start = _parse_date(d.get("start_datetime"))
        event_type = _trim(d.get("event_type"))
        if not cc or not city or not title or not start or not event_type:
            continue
        tags_raw = d.get("tags", [])
        tags = tags_raw if isinstance(tags_raw, list) else _parse_tags(tags_raw)
        out.append(ImportEvent(
            country_code=cc.upper(),
            country_name=_trim(d.get("country_name")),
            city_name=city or "",
            title=title,
            event_type=event_type,
            start_datetime=start,
            description=_trim(d.get("description")),
            venue_name=_trim(d.get("venue_name")),
            address=_trim(d.get("address")),
            end_datetime=_parse_date(d.get("end_datetime")),
            price_text=_trim(d.get("price_text")),
            currency=_trim(d.get("currency")),
            is_free=_parse_bool(d.get("is_free")),
            is_family_friendly=_parse_bool(d.get("is_family_friendly")),
            min_age=_parse_int(d.get("min_age")),
            max_age=_parse_int(d.get("max_age")),
            language_code=_trim(d.get("language_code")),
            external_url=_trim(d.get("external_url")),
            booking_url=_trim(d.get("booking_url")),
            source_url=_trim(d.get("source_url")),
            source_name=_trim(d.get("source_name")),
            trust_tier=_trim(d.get("trust_tier")),
            tags=[str(t).strip() for t in tags if t],
            status=_trim(d.get("status")) or "draft",
            is_visible_to_end_users=_parse_bool(d.get("is_visible_to_end_users")),
            internal_notes=_trim(d.get("internal_notes")),
            review_notes=_trim(d.get("review_notes")),
            external_key=_trim(d.get("external_key")),
            row_num=i + 1,
        ))
    return out


def parse_json_bundle(path: Union[str, Path]) -> ImportBundle:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Bundle must be a JSON object")
    return ImportBundle(
        categories=parse_json_categories(data.get("categories") or []),
        tags=parse_json_tags(data.get("tags") or []),
        sources=parse_json_sources(data.get("sources") or []),
        resources=parse_json_resources(data.get("resources") or []),
        events=parse_json_events(data.get("events") or []),
    )
