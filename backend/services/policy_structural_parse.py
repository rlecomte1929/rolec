"""
Structural extraction only: bytes + MIME → page-aware elements (text, table rows, provenance).

Domain mapping, canonical LTA classification, and normalization remain in other modules.
Optional backends (Docling, Unstructured) are placeholders until explicitly wired and deps approved.

Env:
  RELOPASS_STRUCTURAL_PARSE_BACKEND=native|docling|unstructured  (default: native)
"""
from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

ENV_STRUCTURAL_BACKEND = "RELOPASS_STRUCTURAL_PARSE_BACKEND"


class StructuralParseBackend(str, Enum):
    """Which engine performs document → elements (not semantic mapping)."""

    NATIVE = "native"
    DOCLING = "docling"
    UNSTRUCTURED = "unstructured"


def _normalize_backend(name: Optional[str]) -> StructuralParseBackend:
    if not name or not str(name).strip():
        return StructuralParseBackend.NATIVE
    key = str(name).strip().lower()
    for b in StructuralParseBackend:
        if b.value == key:
            return b
    log.warning("Unknown structural parse backend %r; using native", name)
    return StructuralParseBackend.NATIVE


def _ensure_element_shape(items: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    """Attach optional provenance; required keys unchanged for downstream."""
    out: List[Dict[str, Any]] = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        row = dict(it)
        row.setdefault("text", "")
        row.setdefault("page", 1)
        row.setdefault("is_table_row", False)
        row["structural_source"] = source
        row.setdefault("element_index", i)
        out.append(row)
    return out


def _parse_native(data: bytes, mime_type: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    from .policy_document_clauses import extract_lines_with_pages

    items, err = extract_lines_with_pages(data, mime_type)
    if err:
        return [], err
    return _ensure_element_shape(list(items), StructuralParseBackend.NATIVE.value), None


def _parse_docling_placeholder(
    data: bytes,
    mime_type: str,
    *,
    fallback_on_error: bool,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    TODO: Optional Docling adapter.

    Expected steps when implemented:
    - Run Docling on bytes (likely via subprocess or dedicated worker for heavy deps).
    - Map DoclingDocument / export JSON to ReloPass elements (text, page, is_table_row).
    - Preserve reading order; set table_id / row_index when available.
    """
    _ = (data, mime_type)
    msg = "Docling backend not integrated (install adapter + pin deps; see docs/policy/structural-parsing-integration.md)"
    log.info("structural_parse: %s", msg)
    if fallback_on_error:
        return _parse_native(data, mime_type)
    return [], msg


def _parse_unstructured_placeholder(
    data: bytes,
    mime_type: str,
    *,
    fallback_on_error: bool,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    TODO: Optional Unstructured partition adapter.

    Expected steps when implemented:
    - partition(filename=...) or partition(file=io.BytesIO) with strategy auto / hi_res.
    - Map Table / Title / NarrativeText elements to ReloPass rows; tables → is_table_row=True.
    """
    _ = (data, mime_type)
    msg = "Unstructured backend not integrated (install unstructured + see docs/policy/structural-parsing-integration.md)"
    log.info("structural_parse: %s", msg)
    if fallback_on_error:
        return _parse_native(data, mime_type)
    return [], msg


def parse_policy_document_to_elements(
    data: bytes,
    mime_type: str,
    *,
    backend: Optional[StructuralParseBackend] = None,
    fallback_on_error: bool = True,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Convert a policy file to structured line/table elements for segmentation.

    Does not perform benefit mapping or canonicalization.

    Returns:
        (elements, error). On partial failure with fallback_on_error, error may be None
        after successful native fallback.
    """
    be = backend or _normalize_backend(os.environ.get(ENV_STRUCTURAL_BACKEND))

    if be == StructuralParseBackend.NATIVE:
        return _parse_native(data, mime_type)
    if be == StructuralParseBackend.DOCLING:
        return _parse_docling_placeholder(data, mime_type, fallback_on_error=fallback_on_error)
    if be == StructuralParseBackend.UNSTRUCTURED:
        return _parse_unstructured_placeholder(data, mime_type, fallback_on_error=fallback_on_error)

    return _parse_native(data, mime_type)
