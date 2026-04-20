"""
Context-aware chunking for canonical policy documents.
"""
from __future__ import annotations

import math
import os
import re
from typing import Any, Dict, List, Optional

from ..database import Database
from .policy_canonical_ingestion import resolve_policy_source_bytes
from .policy_structural_parse import parse_policy_document_to_elements


def _looks_like_heading(text: str) -> bool:
    s = text.strip()
    if not s or len(s) > 140:
        return False
    if s.isupper() and len(s) > 3:
        return True
    if re.match(r"^(?:\d+(?:\.\d+)*|[A-Z][\).])\s+", s):
        return True
    return len(s.split()) <= 12 and not s.endswith(".")


def _structure_type(item: Dict[str, Any]) -> str:
    if item.get("is_table_row"):
        return "table_row"
    text = str(item.get("text") or "")
    if _looks_like_heading(text):
        return "heading"
    if re.match(r"^(?:[-*•]|\d+[.)])\s+", text.strip()):
        return "list_item"
    return "paragraph"


def _derive_section_path(stack: List[str]) -> Optional[str]:
    clean = [part.strip() for part in stack if part and part.strip()]
    return " > ".join(clean) if clean else None


def _chunk_limits() -> tuple[int, int]:
    max_words = int(os.getenv("RELOPASS_POLICY_CHUNK_WORDS", "800"))
    overlap_pct = float(os.getenv("RELOPASS_POLICY_CHUNK_OVERLAP", "0.2"))
    overlap_words = max(0, int(math.floor(max_words * overlap_pct)))
    return max_words, overlap_words


def build_canonical_chunks_from_elements(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    max_words, overlap_words = _chunk_limits()
    chunks: List[Dict[str, Any]] = []
    heading_stack: List[str] = []
    current_items: List[Dict[str, Any]] = []
    current_words = 0
    char_cursor = 0

    def flush_chunk() -> None:
        nonlocal current_items, current_words, char_cursor
        if not current_items:
            return
        text_parts = [str(item.get("text") or "").strip() for item in current_items if str(item.get("text") or "").strip()]
        if not text_parts:
            current_items = []
            current_words = 0
            return
        text_content = "\n".join(text_parts)
        structure_types = [str(item.get("structure_type") or "paragraph") for item in current_items]
        dominant_structure = structure_types[0] if len(set(structure_types)) == 1 else "mixed"
        chunk = {
            "chunk_index": len(chunks),
            "section_path": _derive_section_path(heading_stack),
            "structure_type": dominant_structure,
            "page_number": current_items[0].get("page"),
            "char_start": char_cursor,
            "char_end": char_cursor + len(text_content),
            "text_content": text_content,
            "metadata_json": {
                "element_count": len(current_items),
                "structure_types": structure_types,
            },
        }
        chunks.append(chunk)
        char_cursor = chunk["char_end"] + 1
        overlap_items: List[Dict[str, Any]] = []
        if overlap_words > 0:
            running = 0
            for item in reversed(current_items):
                words = len(str(item.get("text") or "").split())
                overlap_items.insert(0, item)
                running += words
                if running >= overlap_words:
                    break
        current_items = overlap_items
        current_words = sum(len(str(item.get("text") or "").split()) for item in current_items)

    for raw_item in elements:
        item = dict(raw_item)
        item["structure_type"] = _structure_type(item)
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        if item["structure_type"] == "heading":
            flush_chunk()
            heading_stack = [text]
            continue
        words = len(text.split())
        if current_items and (current_words + words > max_words):
            flush_chunk()
        current_items.append(item)
        current_words += words
    flush_chunk()
    return chunks


def canonical_chunks_to_assistant_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "id": chunk.get("id"),
            "chunk_index": chunk.get("chunk_index"),
            "text_content": chunk.get("text_content"),
            "section_title": chunk.get("section_path"),
            "page_number": chunk.get("page_number"),
        }
        for chunk in chunks
    ]


def chunk_canonical_policy_document(
    db: Database,
    canonical_document_id: str,
) -> List[Dict[str, Any]]:
    document = db.get_canonical_policy_document(canonical_document_id)
    if not document:
        raise RuntimeError("canonical_policy_document_not_found")

    source_doc_id = document.get("source_policy_document_id")
    company_id = str(document.get("company_id") or "").strip()
    source_uri = str(document.get("source_uri") or "")
    file_path = source_uri if source_uri.startswith("/") else None
    try:
        data, _source_doc = resolve_policy_source_bytes(
            db,
            file_path=file_path,
            source_policy_document_id=source_doc_id,
        )
        elements, err = parse_policy_document_to_elements(data, str(document.get("mime_type") or ""))
        if err:
            raise RuntimeError(err)
        chunks = build_canonical_chunks_from_elements(elements)
    except Exception:
        lines = [line for line in str(document.get("normalized_text") or "").splitlines() if line.strip()]
        fallback_elements = [{"text": line, "page": 1, "is_table_row": False} for line in lines]
        chunks = build_canonical_chunks_from_elements(fallback_elements)

    db.delete_canonical_policy_artifacts(canonical_document_id)
    stored: List[Dict[str, Any]] = []
    for chunk in chunks:
        chunk_id = db.insert_canonical_policy_document_chunk(
            company_id=company_id,
            canonical_policy_document_id=canonical_document_id,
            chunk_index=int(chunk["chunk_index"]),
            section_path=chunk.get("section_path"),
            structure_type=chunk.get("structure_type"),
            page_number=chunk.get("page_number"),
            char_start=chunk.get("char_start"),
            char_end=chunk.get("char_end"),
            text_content=str(chunk.get("text_content") or ""),
            metadata_json=chunk.get("metadata_json") or {},
        )
        stored.append(
            {
                "id": chunk_id,
                **chunk,
            }
        )
    db.update_canonical_policy_document(canonical_document_id, extraction_status="chunked")
    return stored
