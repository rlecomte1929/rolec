"""
Canonical policy ingestion: source bytes -> normalized canonical document row.
"""
from __future__ import annotations

import os
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from ..database import Database
from .policy_document_intake import classify_document, extract_metadata, extract_text_from_bytes
from .policy_storage_paths import BUCKET_HR_POLICIES, normalize_policy_storage_object_key
from .policy_structural_parse import parse_policy_document_to_elements
from .supabase_client import get_supabase_admin_client


def _dedupe_page_headers_and_footers(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    per_page: Dict[int, List[Dict[str, Any]]] = {}
    for item in elements:
        page = int(item.get("page") or 1)
        per_page.setdefault(page, []).append(item)

    header_candidates = Counter()
    footer_candidates = Counter()
    for items in per_page.values():
        if items:
            header_candidates[str(items[0].get("text") or "").strip()] += 1
            footer_candidates[str(items[-1].get("text") or "").strip()] += 1

    repeated_headers = {
        text for text, count in header_candidates.items() if text and count > 1 and len(text) <= 120
    }
    repeated_footers = {
        text for text, count in footer_candidates.items() if text and count > 1 and len(text) <= 120
    }
    out: List[Dict[str, Any]] = []
    for item in elements:
        text = str(item.get("text") or "").strip()
        if text in repeated_headers or text in repeated_footers:
            continue
        out.append(item)
    return out


def _normalize_text_lines(lines: List[str]) -> str:
    return "\n".join(line.strip() for line in lines if str(line).strip())


def _assignment_types_from_inputs(
    explicit_assignment_types: Optional[List[str]],
    metadata: Dict[str, Any],
) -> List[str]:
    if explicit_assignment_types:
        return list(dict.fromkeys([str(item).strip() for item in explicit_assignment_types if str(item).strip()]))
    mentioned = metadata.get("mentioned_assignment_types")
    if isinstance(mentioned, list):
        return list(dict.fromkeys([str(item).strip() for item in mentioned if str(item).strip()]))
    return []


def _download_existing_policy_bytes(source_policy_document: Dict[str, Any]) -> bytes:
    path = str(source_policy_document.get("storage_path") or "")
    key = normalize_policy_storage_object_key(path)
    if not key:
        raise RuntimeError("missing_storage_path")
    supabase = get_supabase_admin_client()
    return supabase.storage.from_(BUCKET_HR_POLICIES).download(key)


def resolve_policy_source_bytes(
    db: Database,
    *,
    file_path: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    source_policy_document_id: Optional[str] = None,
) -> Tuple[bytes, Optional[Dict[str, Any]]]:
    if file_bytes is not None:
        return file_bytes, None
    if file_path:
        with open(file_path, "rb") as fh:
            return fh.read(), None
    if source_policy_document_id:
        source_doc = db.get_policy_document(source_policy_document_id)
        if not source_doc:
            raise RuntimeError("source_policy_document_not_found")
        return _download_existing_policy_bytes(source_doc), source_doc
    raise RuntimeError("no_policy_source_provided")


def ingest_canonical_policy_document(
    db: Database,
    *,
    company_id: Optional[str] = None,
    file_path: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    source_policy_document_id: Optional[str] = None,
    source_uri: Optional[str] = None,
    filename: Optional[str] = None,
    mime_type: Optional[str] = None,
    default_currency: Optional[str] = None,
    assignment_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    data, source_doc = resolve_policy_source_bytes(
        db,
        file_path=file_path,
        file_bytes=file_bytes,
        source_policy_document_id=source_policy_document_id,
    )
    detected_filename = filename or (
        os.path.basename(file_path) if file_path else (source_doc or {}).get("filename")
    )
    detected_mime_type = mime_type or str((source_doc or {}).get("mime_type") or "")
    resolved_company_id = str(company_id or (source_doc or {}).get("company_id") or "").strip()
    if not resolved_company_id:
        raise RuntimeError("company_id is required for canonical policy ingestion")

    lines, err = extract_text_from_bytes(data, detected_mime_type)
    if err:
        raise RuntimeError(err)
    doc_type, policy_scope, _needs_review = classify_document(lines)
    metadata = extract_metadata(lines)
    elements, structural_err = parse_policy_document_to_elements(data, detected_mime_type)
    cleaned_elements = _dedupe_page_headers_and_footers(elements) if not structural_err else []
    normalized_lines = [str(item.get("text") or "").strip() for item in cleaned_elements] or lines
    normalized_text = _normalize_text_lines(normalized_lines)
    canonical_doc_id = db.insert_canonical_policy_document(
        company_id=resolved_company_id,
        source_policy_document_id=source_policy_document_id,
        source_type="existing_policy_document" if source_policy_document_id else "local_file",
        source_uri=source_uri or file_path or str((source_doc or {}).get("storage_path") or ""),
        filename=detected_filename,
        mime_type=detected_mime_type,
        title=metadata.get("detected_title"),
        policy_scope=policy_scope,
        document_type=doc_type,
        version_label=metadata.get("detected_version"),
        effective_date=metadata.get("detected_effective_date"),
        default_currency=default_currency or os.getenv("RELOPASS_POLICY_DEFAULT_CURRENCY") or "USD",
        assignment_types=_assignment_types_from_inputs(assignment_types, metadata),
        raw_text=_normalize_text_lines(lines),
        normalized_text=normalized_text,
        metadata_json={
            **metadata,
            "structural_elements_count": len(cleaned_elements),
            "structural_parse_error": structural_err,
        },
        ingestion_status="ingested",
        extraction_status="pending",
    )
    return db.get_canonical_policy_document(canonical_doc_id) or {"id": canonical_doc_id}
