"""
Import execution layer. Performs DB writes in correct order with upsert logic.
Admin-only; uses get_supabase_admin_client.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from .report import EntityReport, ImportReport
from .schemas import ImportBundle, ImportCategory, ImportEvent, ImportResource, ImportSource, ImportTag
from .transformers import (
    to_category_row,
    to_event_row,
    to_resource_row,
    to_source_row,
    to_tag_row,
)


def _get_supabase():
    from backend.services.supabase_client import get_supabase_admin_client
    return get_supabase_admin_client()


IMPORT_ACTOR_ID = "import-service"  # Used when no real user (CLI)


def _ensure_user_id(user_id: Optional[str]) -> str:
    return user_id or IMPORT_ACTOR_ID


def _load_category_map(supabase) -> Dict[str, str]:
    r = supabase.table("resource_categories").select("id, key").execute()
    return {row["key"]: row["id"] for row in (r.data or [])}


def _load_tag_map(supabase) -> Dict[str, str]:
    r = supabase.table("resource_tags").select("id, key").execute()
    return {row["key"]: row["id"] for row in (r.data or [])}


def _load_source_map(supabase) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Returns (source_name->id, url->id) for resolution."""
    r = supabase.table("resource_sources").select("id, source_name, url").execute()
    by_name: Dict[str, str] = {}
    by_url: Dict[str, str] = {}
    for row in (r.data or []):
        by_name[row["source_name"]] = row["id"]
        if row.get("url"):
            by_url[row["url"]] = row["id"]
    return by_name, by_url


def _resolve_source_id(
    source_name: Optional[str],
    source_url: Optional[str],
    by_name: Dict[str, str],
    by_url: Dict[str, str],
) -> Optional[str]:
    if source_url and source_url in by_url:
        return by_url[source_url]
    if source_name and source_name in by_name:
        return by_name[source_name]
    return None


def _resolve_tag_ids(tag_keys: List[str], tag_map: Dict[str, str]) -> List[str]:
    return [tag_map[k] for k in tag_keys if k in tag_map]


def _status_and_visible(
    status: str,
    is_visible: bool,
    mode: str,
    allow_published: bool,
) -> Tuple[str, bool]:
    if mode == "draft_only":
        return "draft", False
    if mode == "preserve_status" or mode == "allow_published":
        if status == "published" and allow_published:
            return "published", is_visible
        if status in ("draft", "in_review", "approved", "archived"):
            return status, is_visible
    return "draft", False


def execute_categories(
    items: List[ImportCategory],
    user_id: str,
    file_name: str = "",
) -> Tuple[EntityReport, Dict[str, str]]:
    supabase = _get_supabase()
    uid = _ensure_user_id(user_id)
    started = datetime.now(timezone.utc).isoformat()
    report = EntityReport(entity_type="categories", file_name=file_name, started_at=started, rows_read=len(items))
    category_map = _load_category_map(supabase)

    for c in items:
        row = to_category_row(c, uid)
        try:
            r = supabase.table("resource_categories").upsert(
                [row],
                on_conflict="key",
            ).execute()
            data = (r.data or [{}])[0]
            if data.get("id"):
                if c.key in category_map:
                    report.updated += 1
                else:
                    report.inserted += 1
                    category_map[c.key] = data["id"]
            else:
                report.skipped += 1
        except Exception as e:
            report.failed += 1
            report.row_errors.append({"row_num": c.row_num, "message": str(e)})

    report.finished_at = datetime.now(timezone.utc).isoformat()
    return report, _load_category_map(supabase)


def execute_tags(
    items: List[ImportTag],
    user_id: str,
    file_name: str = "",
) -> Tuple[EntityReport, Dict[str, str]]:
    supabase = _get_supabase()
    uid = _ensure_user_id(user_id)
    started = datetime.now(timezone.utc).isoformat()
    report = EntityReport(entity_type="tags", file_name=file_name, started_at=started, rows_read=len(items))
    tag_map = _load_tag_map(supabase)

    for t in items:
        row = to_tag_row(t, uid)
        try:
            r = supabase.table("resource_tags").upsert(
                [row],
                on_conflict="key",
            ).execute()
            data = (r.data or [{}])[0]
            if data.get("id"):
                if t.key in tag_map:
                    report.updated += 1
                else:
                    report.inserted += 1
                    tag_map[t.key] = data["id"]
            else:
                report.skipped += 1
        except Exception as e:
            report.failed += 1
            report.row_errors.append({"row_num": t.row_num, "message": str(e)})

    report.finished_at = datetime.now(timezone.utc).isoformat()
    return report, _load_tag_map(supabase)


def execute_sources(
    items: List[ImportSource],
    user_id: str,
    file_name: str = "",
) -> Tuple[EntityReport, Dict[str, str], Dict[str, str]]:
    supabase = _get_supabase()
    uid = _ensure_user_id(user_id)
    started = datetime.now(timezone.utc).isoformat()
    report = EntityReport(entity_type="sources", file_name=file_name, started_at=started, rows_read=len(items))
    by_name, by_url = _load_source_map(supabase)

    for s in items:
        row = to_source_row(s, uid)
        try:
            r = supabase.table("resource_sources").upsert(
                [row],
                on_conflict="source_name",
            ).execute()
            data = (r.data or [{}])[0]
            if data.get("id"):
                if s.source_name in by_name:
                    report.updated += 1
                else:
                    report.inserted += 1
                    by_name[s.source_name] = data["id"]
                    if s.url:
                        by_url[s.url] = data["id"]
            else:
                report.skipped += 1
        except Exception as e:
            report.failed += 1
            report.row_errors.append({"row_num": s.row_num, "message": str(e)})

    report.finished_at = datetime.now(timezone.utc).isoformat()
    by_name2, by_url2 = _load_source_map(supabase)
    return report, by_name2, by_url2


def execute_resources(
    items: List[ImportResource],
    category_map: Dict[str, str],
    tag_map: Dict[str, str],
    by_name: Dict[str, str],
    by_url: Dict[str, str],
    user_id: str,
    mode: str = "draft_only",
    allow_published: bool = False,
    file_name: str = "",
) -> EntityReport:
    supabase = _get_supabase()
    uid = _ensure_user_id(user_id)
    started = datetime.now(timezone.utc).isoformat()
    report = EntityReport(entity_type="resources", file_name=file_name, started_at=started, rows_read=len(items))

    for r in items:
        cat_id = category_map.get(r.category_key)
        if not cat_id:
            report.failed += 1
            report.row_errors.append({"row_num": r.row_num, "message": f"Category '{r.category_key}' not found"})
            continue
        source_id = _resolve_source_id(r.source_name, r.source_url, by_name, by_url)
        tag_ids = _resolve_tag_ids(r.tags or [], tag_map)
        status, is_visible = _status_and_visible(r.status, r.is_visible_to_end_users, mode, allow_published)
        external_key = r.external_key
        row = to_resource_row(r, cat_id, source_id, tag_ids, uid, status, is_visible, external_key)

        try:
            existing_id = None
            if external_key:
                ex = supabase.table("country_resources").select("id").eq("external_key", external_key).limit(1).execute()
                if ex.data and len(ex.data) > 0:
                    existing_id = ex.data[0]["id"]
            if not existing_id:
                ex = (
                    supabase.table("country_resources")
                    .select("id")
                    .eq("country_code", r.country_code)
                    .eq("city_name", r.city_name or "")
                    .eq("category_id", cat_id)
                    .eq("title", r.title)
                    .limit(1)
                    .execute()
                )
                if ex.data and len(ex.data) > 0:
                    existing_id = ex.data[0]["id"]

            if existing_id:
                upd = {k: v for k, v in row.items() if k not in ("id", "created_at", "created_by_user_id")}
                supabase.table("country_resources").update(upd).eq("id", existing_id).execute()
                supabase.table("country_resource_tags").delete().eq("resource_id", existing_id).execute()
                for tid in tag_ids:
                    supabase.table("country_resource_tags").insert({"resource_id": existing_id, "tag_id": tid}).execute()
                report.updated += 1
            else:
                ins = {k: v for k, v in row.items() if k != "tag_ids"}
                res = supabase.table("country_resources").insert(ins).execute()
                created = (res.data or [{}])[0]
                rid = created.get("id")
                if rid:
                    for tid in tag_ids:
                        supabase.table("country_resource_tags").insert({"resource_id": rid, "tag_id": tid}).execute()
                    report.inserted += 1
                else:
                    report.skipped += 1
        except Exception as e:
            report.failed += 1
            report.row_errors.append({"row_num": r.row_num, "message": str(e)})

    report.finished_at = datetime.now(timezone.utc).isoformat()
    return report


def execute_events(
    items: List[ImportEvent],
    tag_map: Dict[str, str],
    by_name: Dict[str, str],
    by_url: Dict[str, str],
    user_id: str,
    mode: str = "draft_only",
    allow_published: bool = False,
    file_name: str = "",
) -> EntityReport:
    supabase = _get_supabase()
    uid = _ensure_user_id(user_id)
    started = datetime.now(timezone.utc).isoformat()
    report = EntityReport(entity_type="events", file_name=file_name, started_at=started, rows_read=len(items))

    for e in items:
        source_id = _resolve_source_id(e.source_name, e.source_url, by_name, by_url)
        tag_ids = _resolve_tag_ids(e.tags or [], tag_map)
        status, is_visible = _status_and_visible(e.status, e.is_visible_to_end_users, mode, allow_published)
        external_key = e.external_key
        row = to_event_row(e, source_id, tag_ids, uid, status, is_visible, external_key)

        try:
            existing_id = None
            if external_key:
                ex = supabase.table("rkg_country_events").select("id").eq("external_key", external_key).limit(1).execute()
                if ex.data and len(ex.data) > 0:
                    existing_id = ex.data[0]["id"]
            if not existing_id:
                ex = (
                    supabase.table("rkg_country_events")
                    .select("id")
                    .eq("country_code", e.country_code)
                    .eq("city_name", e.city_name)
                    .eq("title", e.title)
                    .eq("start_datetime", e.start_datetime)
                    .limit(1)
                    .execute()
                )
                if ex.data and len(ex.data) > 0:
                    existing_id = ex.data[0]["id"]

            if existing_id:
                upd = {k: v for k, v in row.items() if k not in ("id", "created_at", "created_by_user_id")}
                supabase.table("rkg_country_events").update(upd).eq("id", existing_id).execute()
                supabase.table("country_event_tags").delete().eq("event_id", existing_id).execute()
                for tid in tag_ids:
                    supabase.table("country_event_tags").insert({"event_id": existing_id, "tag_id": tid}).execute()
                report.updated += 1
            else:
                ins = {k: v for k, v in row.items() if k != "tag_ids"}
                res = supabase.table("rkg_country_events").insert(ins).execute()
                created = (res.data or [{}])[0]
                eid = created.get("id")
                if eid:
                    for tid in tag_ids:
                        supabase.table("country_event_tags").insert({"event_id": eid, "tag_id": tid}).execute()
                    report.inserted += 1
                else:
                    report.skipped += 1
        except Exception as e:
            report.failed += 1
            report.row_errors.append({"row_num": e.row_num, "message": str(e)})

    report.finished_at = datetime.now(timezone.utc).isoformat()
    return report


def execute_bundle(
    bundle: ImportBundle,
    user_id: Optional[str] = None,
    mode: str = "draft_only",
    allow_published: bool = False,
    file_name: str = "",
) -> ImportReport:
    """
    Execute full bundle import in correct order.
    mode: draft_only | preserve_status | allow_published
    allow_published: only used when mode allows it
    """
    supabase = _get_supabase()
    uid = _ensure_user_id(user_id)
    started = datetime.now(timezone.utc).isoformat()
    report = ImportReport(started_at=started, mode=mode)

    cat_map = _load_category_map(supabase)
    tag_map = _load_tag_map(supabase)
    by_name, by_url = _load_source_map(supabase)

    if bundle.categories:
        r, cat_map = execute_categories(bundle.categories, uid, file_name)
        report.entity_reports.append(r)
    if bundle.tags:
        r, tag_map = execute_tags(bundle.tags, uid, file_name)
        report.entity_reports.append(r)
    if bundle.sources:
        r, by_name, by_url = execute_sources(bundle.sources, uid, file_name)
        report.entity_reports.append(r)
    if bundle.resources:
        r = execute_resources(
            bundle.resources, cat_map, tag_map, by_name, by_url, uid, mode, allow_published, file_name
        )
        report.entity_reports.append(r)
    if bundle.events:
        r = execute_events(
            bundle.events, tag_map, by_name, by_url, uid, mode, allow_published, file_name
        )
        report.entity_reports.append(r)

    report.finished_at = datetime.now(timezone.utc).isoformat()
    ti = sum(x.inserted for x in report.entity_reports)
    tu = sum(x.updated for x in report.entity_reports)
    tf = sum(x.failed for x in report.entity_reports)
    report.summary = f"Inserted: {ti}, Updated: {tu}, Failed: {tf}"
    return report
