"""
Summary-style policy documents: row-based intermediate model before clause DB rows.

One PolicyRowCandidate ≈ one logical business row (component + description + optional section ref).
Section references are provenance only — excluded from summary_text used for hint extraction / mapping.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .policy_document_intake import (
    DOC_TYPE_COMPACT_BENEFIT_MATRIX,
    DOC_TYPE_POLICY_SUMMARY,
    DOC_TYPE_SUMMARY_TABLE,
)

SUMMARY_ROW_DOCUMENT_TYPES = frozenset(
    {
        DOC_TYPE_POLICY_SUMMARY,
        DOC_TYPE_SUMMARY_TABLE,
        DOC_TYPE_COMPACT_BENEFIT_MATRIX,
    }
)

# Standalone section reference (last column often)
_STANDALONE_SECTION_REF_RE = re.compile(r"^\s*(\d+(?:\.\d+){1,3})\s*$")
# Trailing section ref inside a cell
_TRAILING_SECTION_REF_RE = re.compile(r"([\s.;,]+)(\d+(?:\.\d+){1,3})\s*$")
# Numbered heading at line start (context, not a data row)
_NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")

STRATEGY_SUMMARY_TABLE = "summary_table_pipe"


@dataclass
class PolicyRowCandidate:
    row_id: str
    source_document_id: str
    page_number: int
    section_context: Optional[str]
    component_label: Optional[str]
    summary_text: str
    section_reference: Optional[str]
    raw_cells: List[str] = field(default_factory=list)
    raw_fragments: List[str] = field(default_factory=list)
    parse_confidence: float = 0.75
    parser_strategy: str = STRATEGY_SUMMARY_TABLE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def should_use_summary_row_parser(
    policy_context: Optional[Dict[str, Any]],
    items: Sequence[Dict[str, Any]],
) -> bool:
    """
    Gate row-based parsing: document type / metadata, plus minimum table-like signal.
    """
    if not items:
        return False
    ctx = policy_context or {}
    em = ctx.get("extracted_metadata") if isinstance(ctx.get("extracted_metadata"), dict) else {}
    if em.get("force_summary_row_parser") is True:
        return True
    if em.get("parser_profile") == "summary_rows":
        return True
    sub = (em.get("subformat") or "").strip().lower()
    if sub in ("summary_table", "compact_benefit_matrix", "policy_summary"):
        pass  # still require table signal below
    dt = (ctx.get("detected_document_type") or "").strip()
    if dt not in SUMMARY_ROW_DOCUMENT_TYPES and sub not in ("summary_table", "compact_benefit_matrix"):
        return False

    table_like = 0
    for it in items:
        t = (it.get("text") or "").strip()
        if it.get("is_table_row") or (" | " in t and len(t) > 15):
            table_like += 1
    if em.get("likely_table_heavy") and table_like >= 1:
        return True
    return table_like >= 2


def _is_heading_context_line(text: str) -> bool:
    """Section / subsection title — context only, not a standalone rule row."""
    s = text.strip()
    if not s or len(s) > 120 or "|" in s:
        return False
    if re.search(r"\d{3,}", s):
        return False
    if re.search(r"(?:USD|EUR|GBP|CHF|CAD|AUD|%)\b", s, re.I):
        return False
    if _NUMBERED_HEADING_RE.match(s):
        return True
    lower = s.lower()
    # Avoid narrative lines
    if re.search(r"\b(may|will|shall|must|can|could|should|provided|eligible|covered)\b", lower):
        return False
    # Known section-style phrases
    known = (
        "family support",
        "leave and working hours",
        "housing and accommodation",
        "education and schooling",
        "taxation",
        "policy summary",
        "eligibility",
        "long term assignment",
        "short term assignment",
        "benefits overview",
    )
    for phrase in known:
        if lower == phrase or lower.startswith(phrase + ":"):
            return True
    # Short titled lines (2–7 words), title-like, no sentence punctuation
    words = s.split()
    if 2 <= len(words) <= 7 and s[-1] not in ".;:":
        if s[:1].isupper() and not re.search(r"\d", s):
            return True
    return False


def _split_table_cells(text: str) -> List[str]:
    if "|" not in text:
        return [text.strip()] if text.strip() else []
    return [c.strip() for c in text.split("|")]


def _extract_section_ref_from_cells(cells: List[str]) -> Tuple[List[str], Optional[str]]:
    """Pull section ref from last cell if it looks like 2.1 / 6.5.1; strip from prior cell if trailing."""
    if not cells:
        return [], None
    cells = list(cells)
    ref: Optional[str] = None
    last = cells[-1].strip()
    m = _STANDALONE_SECTION_REF_RE.match(last)
    if m:
        ref = m.group(1)
        cells = cells[:-1]
    elif cells:
        last_cell = cells[-1]
        m2 = _TRAILING_SECTION_REF_RE.search(last_cell)
        if m2:
            ref = m2.group(2)
            cells[-1] = last_cell[: m2.start(1)].rstrip()
            if not cells[-1]:
                cells = cells[:-1]
    return cells, ref


def _continuation_line(text: str) -> bool:
    s = text.strip()
    if not s or " | " in s or len(s) > 400:
        return False
    if _is_heading_context_line(s):
        return False
    # Wrapped description continuation
    if s[0].islower():
        return True
    if re.match(r"^[a-z]", s):
        return True
    if s.startswith(("and ", "or ", "including ", "excluding ", "see ", "per ")):
        return True
    return False


def _scrub_hints_for_section_ref(hints: Dict[str, Any], section_reference: Optional[str]) -> None:
    """Remove numeric hints that duplicate the section reference (not monetary caps)."""
    if not section_reference or not hints:
        return
    try:
        ref_val = float(section_reference.strip())
    except ValueError:
        return
    nums = hints.get("candidate_numeric_values")
    if not isinstance(nums, list):
        return
    kept: List[float] = []
    for n in nums:
        try:
            fn = float(n)
        except (TypeError, ValueError):
            kept.append(n)  # type: ignore[arg-type]
            continue
        if abs(fn - ref_val) < 1e-9:
            continue
        kept.append(fn)
    if kept:
        hints["candidate_numeric_values"] = kept
    else:
        hints.pop("candidate_numeric_values", None)


def parse_items_into_summary_row_candidates(
    items: Sequence[Dict[str, Any]],
    source_document_id: str,
) -> List[PolicyRowCandidate]:
    """
    Build row candidates from page-aware items. Headings become section_context only.
    Table rows become candidates; wrapped prose merges into the previous row.
    Does not emit heading-only rows. Returns empty list if no table rows found.
    """
    items_list = [dict(x) for x in items]
    table_indices: List[int] = []
    for i, it in enumerate(items_list):
        t = (it.get("text") or "").strip()
        if it.get("is_table_row") or (" | " in t and len(t) > 15):
            table_indices.append(i)
    if not table_indices:
        return []

    section_context: Optional[str] = None
    candidates: List[PolicyRowCandidate] = []
    row_seq = 0

    i = 0
    while i < len(items_list):
        it = items_list[i]
        text = (it.get("text") or "").strip()
        page = int(it.get("page") or 1)
        is_table = bool(it.get("is_table_row")) or (" | " in text and len(text) > 15)

        if not text:
            i += 1
            continue

        if is_table:
            raw_cells_pipe = [c.strip() for c in text.split("|")]
            cells = [c for c in raw_cells_pipe if c != ""]
            cells, section_ref = _extract_section_ref_from_cells(cells)
            if not cells:
                i += 1
                continue
            component_label: Optional[str] = None
            if len(cells) >= 2:
                component_label = cells[0][:200] if cells[0] else None
                summary_body = " ".join(cells[1:]).strip()
            else:
                summary_body = cells[0].strip()
            # Strip any remaining trailing ref from summary_body
            if summary_body:
                m3 = _TRAILING_SECTION_REF_RE.search(summary_body)
                if m3 and not section_ref:
                    section_ref = m3.group(2)
                    summary_body = summary_body[: m3.start(1)].rstrip()

            summary_text = (summary_body or "").strip()
            raw_frags = [text]
            # Merge following continuation lines
            j = i + 1
            while j < len(items_list):
                nxt = (items_list[j].get("text") or "").strip()
                nxt_table = bool(items_list[j].get("is_table_row")) or (
                    " | " in nxt and len(nxt) > 15
                )
                if nxt_table or not nxt:
                    break
                if _is_heading_context_line(nxt):
                    break
                if _continuation_line(nxt):
                    summary_text = (summary_text + " " + nxt).strip()
                    raw_frags.append(nxt)
                    j += 1
                    continue
                break

            row_seq += 1
            row_id = f"sr-{row_seq:04d}-{page}-{uuid.uuid4().hex[:8]}"
            candidates.append(
                PolicyRowCandidate(
                    row_id=row_id,
                    source_document_id=source_document_id,
                    page_number=page,
                    section_context=section_context,
                    component_label=component_label,
                    summary_text=summary_text,
                    section_reference=section_ref,
                    raw_cells=raw_cells_pipe,
                    raw_fragments=raw_frags,
                    parse_confidence=0.82 if section_ref else 0.74,
                    parser_strategy=STRATEGY_SUMMARY_TABLE,
                )
            )
            i = j
            continue

        if _is_heading_context_line(text):
            # Title only — context for following rows
            m = _NUMBERED_HEADING_RE.match(text)
            if m:
                section_context = m.group(2).strip()[:200]
            else:
                section_context = text[:200]
            i += 1
            continue

        # Non-table, non-heading: skip isolated fragments (no emission)
        i += 1

    return candidates


def summary_row_candidates_to_clause_dicts(
    candidates: Sequence[PolicyRowCandidate],
) -> List[Dict[str, Any]]:
    """
    Map row candidates to policy_document_clauses-shaped dicts (pre-DB insert).

    Rows are mapped through the canonical LTA template mapper (one primary key per row,
    structured sub-values, deduplication by key + section ref + text fingerprint).
    """
    from .policy_document_clauses import _classify_clause, _extract_normalized_hints
    from .policy_row_to_template_mapper import (
        map_and_deduplicate_row_candidates,
        mapped_row_to_hint_json,
    )

    mapped_rows = map_and_deduplicate_row_candidates(candidates)
    out: List[Dict[str, Any]] = []
    for m in mapped_rows:
        prov = m.provenance
        raw_for_mapping = str(prov.get("summary_text") or "")
        section_parts = [
            p for p in (prov.get("section_context"), prov.get("component_label")) if p
        ]
        section_label = (
            " — ".join(section_parts) if section_parts else prov.get("component_label")
        )

        hints = _extract_normalized_hints(raw_for_mapping, False, section_label)
        if not hints:
            hints = {}
        _scrub_hints_for_section_ref(hints, prov.get("section_reference"))
        hints["summary_row_candidate"] = {
            "row_id": prov.get("row_id"),
            "section_reference": prov.get("section_reference"),
            "component_label": prov.get("component_label"),
            "section_context": prov.get("section_context"),
            "parser_strategy": prov.get("parser_strategy"),
            "page_number": prov.get("page_number"),
            "raw_cells": prov.get("raw_cells") or [],
            "merged_row_ids": m.merged_source_row_ids,
        }
        hints["canonical_lta_row_mapping"] = mapped_row_to_hint_json(m)

        ctype, conf = _classify_clause(raw_for_mapping, False)
        pc = float(prov.get("parse_confidence") or 0.75)
        conf = max(conf, pc * 0.9)
        if m.primary_canonical_key and not m.draft_only_unresolved:
            conf = max(conf, 0.86)
        anchor = (raw_for_mapping or str(prov.get("row_id") or ""))[:100]
        out.append(
            {
                "section_label": section_label,
                "section_path": prov.get("section_context"),
                "clause_type": ctype,
                "title": prov.get("component_label"),
                "raw_text": raw_for_mapping,
                "normalized_hint_json": hints,
                "source_page_start": prov.get("page_number"),
                "source_page_end": prov.get("page_number"),
                "source_anchor": anchor,
                "confidence": min(conf, 0.98),
            }
        )
    return out


def try_build_clauses_via_summary_rows(
    items: Sequence[Dict[str, Any]],
    policy_context: Optional[Dict[str, Any]],
) -> Optional[List[Dict[str, Any]]]:
    """
    If gated and parser produced rows, return clause dicts; else None (caller uses legacy segmentation).
    """
    if not should_use_summary_row_parser(policy_context, items):
        return None
    doc_id = str((policy_context or {}).get("id") or (policy_context or {}).get("document_id") or "")
    if not doc_id:
        doc_id = "unknown-doc"
    candidates = parse_items_into_summary_row_candidates(items, doc_id)
    if not candidates:
        return None
    return summary_row_candidates_to_clause_dicts(candidates)
