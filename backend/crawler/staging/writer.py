"""
Write crawler output to staging tables.
Uses Supabase admin client. No direct write to published tables.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..chunkers.chunker import Chunk
from ..extractors.models import StagedEventCandidate, StagedResourceCandidate
from ..fetchers.http_fetcher import FetchResult
from ..parsers.html_parser import ParsedDocument

log = logging.getLogger(__name__)


def _get_supabase():
    try:
        from backend.services.supabase_client import get_supabase_admin_client
        return get_supabase_admin_client()
    except ImportError:
        from ...services.supabase_client import get_supabase_admin_client
        return get_supabase_admin_client()


def write_crawl_run(
    source_scope: str,
    config_snapshot: Optional[Dict] = None,
    initiated_by: Optional[str] = None,
) -> str:
    """Create crawl run record, return id."""
    supabase = _get_supabase()
    row = {
        "source_scope": source_scope,
        "status": "running",
        "config_snapshot": config_snapshot or {},
        "initiated_by": initiated_by,
    }
    r = supabase.table("crawl_runs").insert(row).execute()
    data = (r.data or [{}])[0]
    return data.get("id", str(uuid.uuid4()))


def update_crawl_run(
    run_id: str,
    *,
    status: str = "completed",
    summary: Optional[str] = None,
    errors_count: int = 0,
    warnings_count: int = 0,
    documents_fetched: int = 0,
    chunks_created: int = 0,
    resources_staged: int = 0,
    events_staged: int = 0,
    duplicates_detected: int = 0,
) -> None:
    """Update crawl run with final stats."""
    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("crawl_runs").update({
        "finished_at": now,
        "status": status,
        "summary": summary,
        "errors_count": errors_count,
        "warnings_count": warnings_count,
        "documents_fetched": documents_fetched,
        "chunks_created": chunks_created,
        "resources_staged": resources_staged,
        "events_staged": events_staged,
        "duplicates_detected": duplicates_detected,
    }).eq("id", run_id).execute()


def write_document(
    crawl_run_id: str,
    source_name: str,
    fetch_result: FetchResult,
    country_code: str = "",
    city_name: Optional[str] = None,
    source_type: str = "",
    trust_tier: str = "",
    parsed: Optional[ParsedDocument] = None,
) -> str:
    """Write crawled document, return id."""
    supabase = _get_supabase()
    parse_status = "parsed" if parsed and not parsed.parse_error else ("parse_failed" if parsed and parsed.parse_error else "pending")
    row = {
        "crawl_run_id": crawl_run_id,
        "source_name": source_name,
        "source_url": fetch_result.url,
        "final_url": fetch_result.final_url,
        "country_code": country_code,
        "city_name": city_name,
        "source_type": source_type,
        "trust_tier": trust_tier,
        "content_type": fetch_result.content_type,
        "content_hash": fetch_result.content_hash,
        "fetched_at": fetch_result.fetched_at,
        "page_title": parsed.page_title if parsed else None,
        "http_status": fetch_result.http_status,
        "parse_status": parse_status,
    }
    r = supabase.table("crawled_source_documents").insert(row).execute()
    data = (r.data or [{}])[0]
    return data.get("id", str(uuid.uuid4()))


def write_chunk(
    document_id: str,
    chunk: Chunk,
) -> str:
    """Write chunk, return id."""
    supabase = _get_supabase()
    row = {
        "document_id": document_id,
        "chunk_index": chunk.chunk_index,
        "heading_path": chunk.heading_path,
        "chunk_text": chunk.chunk_text,
        "chunk_hash": chunk.chunk_hash,
        "extracted_metadata": chunk.metadata,
    }
    r = supabase.table("crawled_source_chunks").insert(row).execute()
    data = (r.data or [{}])[0]
    return data.get("id", str(uuid.uuid4()))


def write_resource_candidate(
    crawl_run_id: str,
    document_id: Optional[str],
    chunk_id: Optional[str],
    candidate: StagedResourceCandidate,
) -> str:
    """Write staged resource candidate."""
    supabase = _get_supabase()
    row = {
        "crawl_run_id": crawl_run_id,
        "document_id": document_id,
        "chunk_id": chunk_id,
        "country_code": candidate.country_code,
        "country_name": candidate.country_name,
        "city_name": candidate.city_name,
        "category_key": candidate.category_key,
        "title": candidate.title,
        "summary": candidate.summary,
        "body": candidate.body,
        "content_json": candidate.content_json,
        "resource_type": candidate.resource_type,
        "audience_type": candidate.audience_type,
        "tags": candidate.tags,
        "source_url": candidate.source_url,
        "source_name": candidate.source_name,
        "trust_tier": candidate.trust_tier,
        "confidence_score": candidate.confidence_score,
        "extraction_method": candidate.extraction_method,
        "status": "new",
        "provenance_json": candidate.provenance,
    }
    r = supabase.table("staged_resource_candidates").insert(row).execute()
    data = (r.data or [{}])[0]
    return data.get("id", str(uuid.uuid4()))


def write_event_candidate(
    crawl_run_id: str,
    document_id: Optional[str],
    chunk_id: Optional[str],
    candidate: StagedEventCandidate,
) -> str:
    """Write staged event candidate."""
    supabase = _get_supabase()
    row = {
        "crawl_run_id": crawl_run_id,
        "document_id": document_id,
        "chunk_id": chunk_id,
        "country_code": candidate.country_code,
        "country_name": candidate.country_name,
        "city_name": candidate.city_name,
        "title": candidate.title,
        "description": candidate.description,
        "event_type": candidate.event_type,
        "venue_name": candidate.venue_name,
        "address": candidate.address,
        "start_datetime": candidate.start_datetime,
        "end_datetime": candidate.end_datetime,
        "price_text": candidate.price_text,
        "currency": candidate.currency,
        "is_free": candidate.is_free,
        "is_family_friendly": candidate.is_family_friendly,
        "source_url": candidate.source_url,
        "source_name": candidate.source_name,
        "trust_tier": candidate.trust_tier,
        "confidence_score": candidate.confidence_score,
        "extraction_method": candidate.extraction_method,
        "status": "new",
        "provenance_json": candidate.provenance,
    }
    r = supabase.table("staged_event_candidates").insert(row).execute()
    data = (r.data or [{}])[0]
    return data.get("id", str(uuid.uuid4()))
