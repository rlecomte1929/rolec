"""
Strict source / provenance for policy normalization: section refs (2.1, 6.5.1) are never amounts.

Used by clause hint extraction, normalize_clauses_to_objects, and persisted on Layer-2 metadata_json.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Dotted policy section references (not version years, not large amounts)
_DOTTED_SECTION_NUM_RE = re.compile(r"^\d{1,2}\.\d{1,2}(?:\.\d{1,2})?$")
_SECTION_REF_IN_TEXT_RE = re.compile(
    r"(?:^|[\s:;(,])(\d{1,2}(?:\.\d{1,2}){1,3})(?=[\s.:;,)\]\-]|$)",
)

PROVENANCE_SCHEMA_V1 = "policy_source_v1"


def _format_dotted_number(n: float) -> str:
    if n != n:  # NaN
        return ""
    if abs(n - int(n)) < 1e-9:
        return str(int(n))
    s = f"{n:.4f}".rstrip("0").rstrip(".")
    return s


def looks_like_dotted_section_number(n: float) -> bool:
    """True for 2.1, 6.5, 8.3.1 style values; false for 30, 5000, 15%."""
    if n != n or n < 0 or n >= 1000:
        return False
    s = _format_dotted_number(n)
    if "." not in s:
        return False
    return bool(_DOTTED_SECTION_NUM_RE.match(s))


def should_exclude_numeric_as_section_reference(n: float, raw_text: str) -> bool:
    """
    If True, this numeric must not be used as amount_value / cap hint.
    Excludes dotted section-like numbers unless clearly tied to %, currency, or duration units.
    """
    if not looks_like_dotted_section_number(n):
        return False
    r = raw_text or ""
    token = re.escape(_format_dotted_number(n))
    if re.search(rf"(?:EUR|USD|GBP|CHF|CAD|AUD|SGD|NZD|JPY)\s*{token}\b", r, re.I):
        return False
    if re.search(rf"\b{token}\s*%", r):
        return False
    if re.search(rf"\b{token}\s*(?:days?|weeks?|months?|years?)\b", r, re.I):
        return False
    if re.search(rf"\b{token}\s*(?:nights?)\b", r, re.I):
        return False
    return True


def filter_candidate_numeric_values(nums: List[Any], raw_text: str) -> List[float]:
    """Drop section-reference-like numbers from Layer-1 hint list."""
    out: List[float] = []
    for n in nums:
        try:
            fn = float(n)
        except (TypeError, ValueError):
            continue
        if should_exclude_numeric_as_section_reference(fn, raw_text):
            continue
        if 0 < fn < 1e12:
            out.append(fn)
    return list(dict.fromkeys(out))[:10]


def apply_numeric_filter_to_hints(hints: Dict[str, Any], raw_text: str) -> None:
    """Mutate hints: filter candidate_numeric_values in place."""
    nums = hints.get("candidate_numeric_values")
    if not isinstance(nums, list) or not nums:
        return
    filtered = filter_candidate_numeric_values(nums, raw_text)
    if filtered:
        hints["candidate_numeric_values"] = filtered
    else:
        hints.pop("candidate_numeric_values", None)


def primary_section_reference_from_hints(hints: Dict[str, Any]) -> Optional[str]:
    sr = hints.get("summary_row_candidate")
    if isinstance(sr, dict):
        ref = sr.get("section_reference")
        if ref is not None and str(ref).strip():
            return str(ref).strip()
    clm = hints.get("canonical_lta_row_mapping")
    if isinstance(clm, dict):
        prov = clm.get("provenance")
        if isinstance(prov, dict):
            ref = prov.get("section_reference")
            if ref is not None and str(ref).strip():
                return str(ref).strip()
    sp = hints.get("source_provenance")
    if isinstance(sp, dict):
        ref = sp.get("section_ref")
        if ref is not None and str(ref).strip():
            return str(ref).strip()
    return None


def primary_section_reference_from_text(raw_text: str) -> Optional[str]:
    """Best-effort: last dotted token that matches section pattern in text."""
    if not (raw_text or "").strip():
        return None
    found = _SECTION_REF_IN_TEXT_RE.findall(raw_text)
    if not found:
        return None
    for cand in reversed(found):
        if _DOTTED_SECTION_NUM_RE.match(cand):
            return cand
    return None


def resolve_section_reference(
    hints: Dict[str, Any],
    raw_text: str,
) -> Optional[str]:
    """Provenance-only section ref: summary row wins, else text parse."""
    from_hints = primary_section_reference_from_hints(hints)
    if from_hints:
        return from_hints
    return primary_section_reference_from_text(raw_text)


def strip_section_reference_tokens_for_display(text: str) -> str:
    """
    Remove standalone section-ref tokens from HR/employee-facing description text.
    Does not remove '30 days' or currency amounts.
    """
    if not text:
        return text
    out = text
    # Trailing " 2.1" or " (6.5)"
    out = re.sub(
        r"(?:\s*[\(]?\s*(\d{1,2}(?:\.\d{1,2}){1,3})\s*\)?\s*)$",
        "",
        out.strip(),
        flags=re.I,
    )
    # "section 2.1" at end
    out = re.sub(
        r"\s*,?\s*(?:section|sec\.?|§)\s*(\d{1,2}(?:\.\d{1,2}){1,3})\s*$",
        "",
        out,
        flags=re.I,
    )
    return out.strip()


def build_source_provenance(
    *,
    document_id: str,
    page_start: Optional[Any],
    page_end: Optional[Any],
    section_ref: Optional[str],
    source_label: Optional[str],
    source_excerpt: str,
    clause_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "schema": PROVENANCE_SCHEMA_V1,
        "document_id": document_id,
        "page": page_start,
        "page_end": page_end,
        "section_ref": section_ref,
        "source_label": (source_label or "")[:500] if source_label else None,
        "source_excerpt": (source_excerpt or "")[:2000],
        "clause_id": clause_id,
    }


def scrub_amount_if_section_reference(
    amount_value: Optional[float],
    raw_text: str,
    hints: Dict[str, Any],
) -> Optional[float]:
    """Clear amount_value when it is only a section reference, not a limit."""
    if amount_value is None:
        return None
    try:
        av = float(amount_value)
    except (TypeError, ValueError):
        return amount_value
    if should_exclude_numeric_as_section_reference(av, raw_text):
        return None
    # Cross-check: summary row ref string matches formatted amount
    ref = resolve_section_reference(hints, raw_text)
    if ref and _format_dotted_number(av) == ref:
        return None
    return amount_value


def merge_provenance_into_metadata(
    metadata_json: Dict[str, Any],
    provenance: Dict[str, Any],
) -> Dict[str, Any]:
    """Attach source_provenance without dropping existing keys (e.g. reimbursement_logic)."""
    m = dict(metadata_json or {})
    m["source_provenance"] = provenance
    return m
