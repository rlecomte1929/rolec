"""
Change detection service: compare documents across crawl runs.
Classifies changes as new, unchanged, minor, significant.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)


def _get_supabase():
    return get_supabase_admin_client()


def _normalize_text(s: str) -> str:
    """Normalize text for comparison (strip, lower, collapse whitespace)."""
    return " ".join((s or "").lower().split())


def _normalized_content_hash(text: str) -> str:
    """Hash of normalized text - reduces boilerplate noise."""
    return hashlib.sha256(_normalize_text(text).encode("utf-8", errors="replace")).hexdigest()


def _find_previous_document(
    source_name: str,
    source_url: str,
    exclude_crawl_run_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Find most recent document for same source+url from earlier runs."""
    supabase = _get_supabase()
    url = (source_url or "").strip()
    q = supabase.table("crawled_source_documents").select(
        "id, content_hash, page_title, created_at, crawl_run_id, final_url, source_url"
    ).eq("source_name", source_name)
    if exclude_crawl_run_id:
        q = q.neq("crawl_run_id", exclude_crawl_run_id)
    r = q.order("created_at", desc=True).limit(20).execute()
    for row in (r.data or []):
        if row.get("crawl_run_id") == exclude_crawl_run_id:
            continue
        doc_url = (row.get("final_url") or row.get("source_url") or "").strip()
        if doc_url == url or (not url and not doc_url):
            return row
    return None


def run_change_detection_for_crawl_run(
    crawl_run_id: Optional[str],
    job_run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run change detection for documents in a crawl run.
    Compares each document to previous version (same source+url).
    Writes document_change_events.
    """
    if not crawl_run_id:
        return {"documents_processed": 0, "changes": [], "error": "No crawl_run_id"}

    supabase = _get_supabase()
    docs_r = (
        supabase.table("crawled_source_documents")
        .select("id, source_name, source_url, final_url, content_hash, page_title, country_code, city_name")
        .eq("crawl_run_id", crawl_run_id)
        .execute()
    )
    docs = docs_r.data or []

    crawl_run = supabase.table("crawl_runs").select("id").eq("id", crawl_run_id).limit(1).execute()
    run_exists = (crawl_run.data or [{}])[0].get("id") == crawl_run_id
    if not run_exists:
        return {"documents_processed": 0, "changes": [], "error": "Crawl run not found"}

    changes: List[Dict[str, Any]] = []
    for doc in docs:
        source_name = doc.get("source_name", "")
        url = doc.get("final_url") or doc.get("source_url", "")
        new_hash = doc.get("content_hash") or ""
        prev = _find_previous_document(source_name, url, exclude_crawl_run_id=crawl_run_id)

        change_type = "new"
        prev_hash = None
        prev_doc_id = None
        change_score = 1.0

        if prev:
            prev_doc_id = prev.get("id")
            prev_hash = prev.get("content_hash")
            if prev_hash == new_hash:
                change_type = "unchanged"
                change_score = 0.0
            else:
                change_type = "updated"
                change_score = 0.5
                if prev.get("page_title") != doc.get("page_title"):
                    change_score = 0.8
                change_type = "significant_change" if change_score >= 0.5 else "minor_change"

        event = {
            "job_run_id": job_run_id,
            "crawl_run_id": crawl_run_id,
            "source_document_id": doc.get("id"),
            "source_url": url or doc.get("source_url", ""),
            "source_name": source_name,
            "country_code": doc.get("country_code"),
            "city_name": doc.get("city_name"),
            "previous_document_id": prev_doc_id,
            "previous_content_hash": prev_hash,
            "new_content_hash": new_hash,
            "change_type": change_type,
            "change_score": change_score,
        }
        try:
            supabase.table("document_change_events").insert(event).execute()
            changes.append(event)
        except Exception as e:
            log.warning("Failed to write change event: %s", e)

    return {
        "documents_processed": len(docs),
        "changes_count": len([c for c in changes if c.get("change_type") not in ("unchanged",)]),
        "significant_count": len([c for c in changes if c.get("change_type") == "significant_change"]),
        "changes": changes[:50],
    }


def list_document_changes(
    job_run_id: Optional[str] = None,
    source_name: Optional[str] = None,
    change_type: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List document change events."""
    supabase = _get_supabase()
    q = supabase.table("document_change_events").select("*", count="exact").order("detected_at", desc=True)
    if job_run_id:
        q = q.eq("job_run_id", job_run_id)
    if source_name:
        q = q.eq("source_name", source_name)
    if change_type:
        q = q.eq("change_type", change_type)
    if since:
        q = q.gte("detected_at", since)
    r = q.range(offset, offset + limit - 1).execute()
    return {"items": r.data or [], "total": r.count or 0}


def get_document_change(change_id: str) -> Optional[Dict[str, Any]]:
    supabase = _get_supabase()
    r = supabase.table("document_change_events").select("*").eq("id", change_id).limit(1).execute()
    return (r.data or [None])[0]
