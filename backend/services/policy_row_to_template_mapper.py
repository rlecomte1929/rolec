"""
Map summary row candidates to at most one primary canonical LTA template key per logical row,
with structured sub-values (tiers, variants) and anti-duplication by (key, source_ref, text fingerprint).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .policy_canonical_lta_template import (
    PolicyApplicabilityDimension,
    get_canonical_lta_field,
)
from .policy_canonical_key_matcher import resolve_primary_canonical_lta_key
from .policy_lta_grouping_heuristics import (
    apply_lta_grouping_heuristics_to_mapped_row,
    analyze_compensation_informational,
    merge_lta_pattern_dict,
)
from .policy_summary_row_parser import PolicyRowCandidate

# --- Output model ---


@dataclass
class MappedTemplateRow:
    """One grouped row after mapping + optional merge of duplicate fragments."""

    primary_canonical_key: Optional[str]
    sub_values: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    applicability: List[str] = field(default_factory=list)
    coverage_status: str = "mentioned"
    quantification: Dict[str, Any] = field(default_factory=dict)
    comparison_readiness_hint: str = "partial"
    draft_only_unresolved: bool = False
    normalized_text_fingerprint: str = ""
    merged_source_row_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --- Normalization for dedup ---


def normalize_row_text_for_dedup(
    summary_text: str,
    component_label: Optional[str],
) -> str:
    parts = []
    if component_label:
        parts.append(component_label.strip().lower())
    parts.append((summary_text or "").strip().lower())
    raw = " ".join(p for p in parts if p)
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    raw = re.sub(r"[\s/|]+", " ", raw)
    raw = re.sub(r"[^\w\s]", "", raw)
    return re.sub(r"\s+", " ", raw).strip()


def _combined_text(
    component_label: Optional[str],
    summary_text: str,
    section_context: Optional[str],
) -> str:
    chunks = [
        (component_label or "").strip(),
        (summary_text or "").strip(),
        (section_context or "").strip(),
    ]
    return " ".join(c for c in chunks if c).lower()


# --- Structured sub-values ---

_TIER_ASSIGN_RE = re.compile(
    r"(?:assignee|employee|principal)\s*[:\s]*(?:USD|EUR|GBP|CHF|CAD|AUD)?\s*(?:[€$£]\s*)?([\d,]+(?:\.\d+)?)\b",
    re.I,
)
_TIER_DEP_RE = re.compile(
    r"(?:each\s+)?depend(?:a|e)nt[s]?\s*[:\s]*(?:USD|EUR|GBP|CHF|CAD|AUD)?\s*(?:[€$£]\s*)?([\d,]+(?:\.\d+)?)\b",
    re.I,
)
_DURATION_DAYS_RE = re.compile(
    r"(\d+)\s*(?:days?|d)\b(?:\s+(?:maximum|max|limit))?",
    re.I,
)
_AMOUNT_ANY_RE = re.compile(r"(?:[€$£]\s*)?([\d,]+(?:\.\d+)?)\s*(?:USD|EUR|GBP|CHF)?", re.I)


_SLASH_LEAD_ASSIGN_RE = re.compile(
    r"^\s*([\d,]+(?:\.\d+)?)\s*/\s*(?:each\s+)?depend",
    re.I,
)


def _parse_amount_tiers(summary_text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    tiers: List[Dict[str, Any]] = []
    m_a = _TIER_ASSIGN_RE.search(summary_text)
    m_d = _TIER_DEP_RE.search(summary_text)
    if m_a:
        tiers.append({"role": "assignee", "amount_text": m_a.group(1).replace(",", "")})
    elif m_d and _SLASH_LEAD_ASSIGN_RE.search(summary_text):
        m_lead = _SLASH_LEAD_ASSIGN_RE.match(summary_text)
        if m_lead:
            tiers.append({"role": "assignee", "amount_text": m_lead.group(1).replace(",", "")})
    if m_d:
        tiers.append({"role": "each_dependant", "amount_text": m_d.group(1).replace(",", "")})
    if tiers:
        out["amount_tiers"] = tiers
    return out


def _parse_home_leave_variants(summary_text: str) -> Dict[str, Any]:
    if "/" not in summary_text:
        return {}
    stripped = re.sub(
        r"^\s*home\s+leave\s*[:\s–\-]*",
        "",
        summary_text.strip(),
        flags=re.I,
    )
    parts = [p.strip() for p in re.split(r"\s*/\s*", stripped) if p.strip()]
    if len(parts) < 2:
        return {}
    cleaned = []
    for p in parts:
        pl = re.sub(r"\s+", " ", p.lower())
        if pl in ("home leave", "homeleave"):
            continue
        if len(p) < 4:
            continue
        cleaned.append(p)
    if len(cleaned) >= 2:
        return {"leave_variants": cleaned}
    return {}


def _parse_duration_quant(summary_text: str) -> Dict[str, Any]:
    m = _DURATION_DAYS_RE.search(summary_text)
    if m:
        return {"duration_days": int(m.group(1))}
    return {}


def _external_reference_signals(text_lower: str) -> bool:
    return any(
        x in text_lower
        for x in (
            "third party",
            "third-party",
            "determined by",
            "external data",
            "vendor",
            "provider data",
            "benchmark",
        )
    )


def _immigration_applicability(summary_text: str) -> List[str]:
    lower = summary_text.lower()
    dims: List[str] = []
    if "assignee" in lower or "employee" in lower or "principal" in lower:
        dims.append(PolicyApplicabilityDimension.EMPLOYEE.value)
    if "accompanying" in lower or "family" in lower or "depend" in lower:
        dims.append(PolicyApplicabilityDimension.FAMILY.value)
    if not dims:
        dims = [
            PolicyApplicabilityDimension.EMPLOYEE.value,
            PolicyApplicabilityDimension.FAMILY.value,
        ]
    return sorted(set(dims))


def map_single_row_candidate(rc: PolicyRowCandidate) -> MappedTemplateRow:
    combined = _combined_text(rc.component_label, rc.summary_text, rc.section_context)
    primary = resolve_primary_canonical_lta_key(
        rc.component_label, rc.summary_text, rc.section_context
    )
    fingerprint = normalize_row_text_for_dedup(rc.summary_text, rc.component_label)

    sub_values: Dict[str, Any] = {}
    quant: Dict[str, Any] = {}
    coverage = "mentioned"
    comparison = "partial"
    draft_only = False

    if primary is None:
        comp_info = analyze_compensation_informational(
            combined, rc.component_label or ""
        )
        if comp_info.get("is_informational"):
            primary = "policy_definitions_and_exceptions"
        else:
            draft_only = True
            comparison = "draft_only"
            coverage = "ambiguous"
            return MappedTemplateRow(
                primary_canonical_key=None,
                sub_values={},
                provenance=_provenance_from_candidate(rc),
                applicability=[],
                coverage_status=coverage,
                quantification=quant,
                comparison_readiness_hint=comparison,
                draft_only_unresolved=True,
                normalized_text_fingerprint=fingerprint,
                merged_source_row_ids=[rc.row_id],
            )

    field = get_canonical_lta_field(primary)
    applicability = (
        sorted(a.value for a in field.applicability) if field else []
    )

    text_lower = combined.lower()
    if primary == "relocation_allowance":
        sub_values.update(_parse_amount_tiers(rc.summary_text))
        if sub_values.get("amount_tiers"):
            quant["structured_amounts"] = sub_values["amount_tiers"]
        if _AMOUNT_ANY_RE.search(rc.summary_text):
            coverage = "specified"
        comparison = "ready" if quant else "partial"

    elif primary == "home_leave":
        sub_values.update(_parse_home_leave_variants(rc.summary_text))
        if sub_values.get("leave_variants"):
            comparison = "ready"
            coverage = "specified"
        if "r&r" in text_lower or "rest and recuperation" in text_lower:
            sub_values.setdefault("notes", []).append("includes_R_and_R")

    elif primary == "policy_definitions_and_exceptions":
        comparison = "partial"
        coverage = "mentioned"

    elif primary == "work_permits_and_visas":
        applicability = _immigration_applicability(rc.summary_text)
        comparison = "ready"
        coverage = "specified" if "assignee" in text_lower or "family" in text_lower else "mentioned"

    elif primary == "temporary_living_outbound":
        quant.update(_parse_duration_quant(rc.summary_text))
        if quant.get("duration_days"):
            coverage = "specified"
            comparison = "ready"

    elif primary == "temporary_living_return":
        quant.update(_parse_duration_quant(rc.summary_text))
        comparison = "partial"
        coverage = "mentioned"

    elif primary == "host_transportation":
        comparison = "partial"
        coverage = "mentioned"

    elif primary == "language_training":
        comparison = "partial"
        coverage = "mentioned"

    elif primary == "cultural_training":
        comparison = "partial"
        coverage = "mentioned"

    elif primary == "school_search":
        comparison = "partial"
        coverage = "mentioned"

    elif primary == "tax_equalization":
        comparison = "partial"
        coverage = "mentioned"

    elif primary == "tax_return_support":
        comparison = "partial"
        coverage = "mentioned"

    elif primary == "tax_briefing":
        comparison = "partial"
        coverage = "mentioned"

    elif primary == "spouse_support":
        comparison = "partial"
        coverage = "mentioned"

    elif primary == "host_housing":
        if _external_reference_signals(text_lower) or "capped" in text_lower or "cap " in text_lower:
            coverage = "capped_external"
            comparison = "external_reference"
            sub_values["cap_basis"] = "external_or_third_party"
        else:
            comparison = "partial"

    elif primary == "child_education":
        if "difference" in text_lower or "differential" in text_lower:
            sub_values["reimbursement_logic"] = "difference_only"
            comparison = "partial"
            coverage = "specified"
        if "eligible" in text_lower or "condition" in text_lower:
            sub_values.setdefault("conditions", []).append("eligibility_or_conditions_mentioned")
        if not sub_values:
            comparison = "partial"

    sub_values, applicability, coverage, comparison = apply_lta_grouping_heuristics_to_mapped_row(
        primary_canonical_key=primary,
        summary_text=rc.summary_text,
        component_label=rc.component_label,
        section_context=rc.section_context,
        sub_values=sub_values,
        applicability=applicability,
        coverage_status=coverage,
        comparison_readiness_hint=comparison,
    )

    return MappedTemplateRow(
        primary_canonical_key=primary,
        sub_values=sub_values,
        provenance=_provenance_from_candidate(rc),
        applicability=applicability,
        coverage_status=coverage,
        quantification=quant,
        comparison_readiness_hint=comparison,
        draft_only_unresolved=draft_only,
        normalized_text_fingerprint=fingerprint,
        merged_source_row_ids=[rc.row_id],
    )


def _provenance_from_candidate(rc: PolicyRowCandidate) -> Dict[str, Any]:
    return {
        "row_id": rc.row_id,
        "source_document_id": rc.source_document_id,
        "section_reference": rc.section_reference,
        "section_context": rc.section_context,
        "component_label": rc.component_label,
        "summary_text": rc.summary_text,
        "page_number": rc.page_number,
        "parser_strategy": rc.parser_strategy,
        "raw_cells": list(rc.raw_cells),
        "parse_confidence": rc.parse_confidence,
    }


def _merge_sub_values(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if k not in out:
            out[k] = v
            continue
        if k == "notes" and isinstance(out[k], list) and isinstance(v, list):
            out[k] = sorted(set(out[k] + v))
        elif k == "amount_tiers" and isinstance(out[k], list) and isinstance(v, list):
            seen = {tuple(sorted(d.items())) for d in out[k] if isinstance(d, dict)}
            for item in v:
                if isinstance(item, dict):
                    t = tuple(sorted(item.items()))
                    if t not in seen:
                        seen.add(t)
                        out[k].append(item)
        elif k == "leave_variants" and isinstance(out[k], list) and isinstance(v, list):
            out[k] = sorted(set(out[k] + v), key=lambda x: (len(x), x))
        elif k == "governance_conditions" and isinstance(out[k], list) and isinstance(v, list):
            seen = {tuple(sorted(d.items())) for d in out[k] if isinstance(d, dict)}
            for item in v:
                if isinstance(item, dict):
                    t = tuple(sorted(item.items()))
                    if t not in seen:
                        seen.add(t)
                        out[k].append(item)
        elif k == "lta_domain_patterns" and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = merge_lta_pattern_dict(out[k], v)
        elif k == "family_coverage" and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = {**out[k], **v}
        elif k == "external_governance" and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    return out


def _merge_mapped_rows(target: MappedTemplateRow, other: MappedTemplateRow) -> None:
    target.sub_values = _merge_sub_values(target.sub_values, other.sub_values)
    target.quantification = {**other.quantification, **target.quantification}
    target.merged_source_row_ids.extend(other.merged_source_row_ids)
    target.provenance["merged_row_ids"] = list(dict.fromkeys(target.merged_source_row_ids))
    pc0 = float(target.provenance.get("parse_confidence") or 0)
    pc1 = float(other.provenance.get("parse_confidence") or 0)
    target.provenance["parse_confidence"] = max(pc0, pc1)


def map_and_deduplicate_row_candidates(
    candidates: Sequence[PolicyRowCandidate],
) -> List[MappedTemplateRow]:
    """
    Map each candidate, then merge rows that share the same primary key, source ref, and text fingerprint.
    Unresolved (None key) rows dedupe on ('__unresolved__', source_ref, fingerprint).
    """
    mapped = [map_single_row_candidate(rc) for rc in candidates]
    buckets: Dict[Tuple[str, str, str], MappedTemplateRow] = {}
    order: List[Tuple[str, str, str]] = []
    for m in mapped:
        key = m.primary_canonical_key or "__unresolved__"
        src = (m.provenance.get("section_reference") or "") or ""
        fp = m.normalized_text_fingerprint
        dedup_key = (key, src, fp)
        if dedup_key not in buckets:
            buckets[dedup_key] = m
            order.append(dedup_key)
        else:
            _merge_mapped_rows(buckets[dedup_key], m)
    return [buckets[k] for k in order]


def mapped_row_to_hint_json(m: MappedTemplateRow) -> Dict[str, Any]:
    """Payload for normalized_hint_json['canonical_lta_row_mapping']."""
    tmpl_field = (
        get_canonical_lta_field(m.primary_canonical_key)
        if m.primary_canonical_key
        else None
    )
    return {
        "primary_canonical_key": m.primary_canonical_key,
        "template_value_type": (
            tmpl_field.value_type.value if tmpl_field else None
        ),
        "sub_values": m.sub_values,
        "applicability": m.applicability,
        "coverage_status": m.coverage_status,
        "quantification": m.quantification,
        "comparison_readiness_hint": m.comparison_readiness_hint,
        "draft_only_unresolved": m.draft_only_unresolved,
        "provenance": m.provenance,
        "merged_source_row_ids": m.merged_source_row_ids,
        "normalized_text_fingerprint": m.normalized_text_fingerprint,
    }
