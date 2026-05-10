"""
HR-facing grouped policy review: template domains × collapsed rows (not raw draft explosion).

Builds ``grouped_review`` for the policy-review API from ``grouped_policy_items`` plus
template-first import metadata for empty-slot and review counts.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .policy_canonical_lta_template import get_canonical_lta_field
from .policy_grouped_comparison_readiness import (
    READINESS_COMPARISON_READY,
    READINESS_DETERMINISTIC_NON_BUDGET,
    READINESS_EXTERNAL_REFERENCE_PARTIAL,
    READINESS_INFORMATIONAL_ONLY,
    READINESS_REVIEW_REQUIRED,
)

# (api_domain_key, template domain_id, HR-facing title)
GROUPED_REVIEW_DOMAIN_DEFS: Tuple[Tuple[str, str, str], ...] = (
    ("eligibility_and_scope", "eligibility_and_scope", "Eligibility and scope"),
    ("pre_departure_support", "pre_departure_support", "Pre-departure support"),
    ("move_logistics", "move_logistics", "Move logistics"),
    ("compensation_and_payroll", "compensation_and_payroll", "Compensation and payroll"),
    ("assignment_allowances", "assignment_allowances_and_premiums", "Assignment allowances and premiums"),
    ("family_support", "family_support", "Family support"),
    ("leave_and_travel", "leave_and_travel_during_assignment", "Leave and travel during assignment"),
    ("repatriation", "repatriation", "Repatriation"),
    ("governance", "governance_approvals_external", "Governance, approvals, and external dependencies"),
)

_TEMPLATE_DOMAIN_TO_API_KEY: Dict[str, str] = {t[1]: t[0] for t in GROUPED_REVIEW_DOMAIN_DEFS}

_APPLICABILITY_LABELS = {
    "employee": "Employee",
    "spouse_partner": "Spouse or partner",
    "children": "Children",
    "family": "Family",
    "assignment_type": "Assignment type",
}


def _drafts_by_clause_index(
    draft_rule_candidates: Sequence[Dict[str, Any]],
) -> Dict[int, List[Dict[str, Any]]]:
    out: Dict[int, List[Dict[str, Any]]] = {}
    for d in draft_rule_candidates:
        if not isinstance(d, dict):
            continue
        idx = d.get("clause_index")
        if not isinstance(idx, int):
            continue
        out.setdefault(idx, []).append(d)
    return out


def _api_domain_for_canonical_key(canonical_key: Optional[str]) -> str:
    if not canonical_key or not isinstance(canonical_key, str):
        return "unmapped"
    f = get_canonical_lta_field(canonical_key)
    if not f:
        return "unmapped"
    return _TEMPLATE_DOMAIN_TO_API_KEY.get(f.domain_id, "unmapped")


def _applicability_summary(dims: Sequence[str]) -> Optional[str]:
    if not dims:
        return None
    labels = [_APPLICABILITY_LABELS.get(str(d), str(d).replace("_", " ").title()) for d in dims if d]
    if not labels:
        return None
    return ", ".join(labels)


def _imported_value_summary(item: Dict[str, Any]) -> str:
    bd = item.get("business_display") if isinstance(item.get("business_display"), dict) else {}
    parts: List[str] = []
    sp = bd.get("summary_paragraph")
    if isinstance(sp, str) and sp.strip():
        parts.append(sp.strip()[:1200])
    for line in bd.get("tier_lines") or []:
        if isinstance(line, str) and line.strip():
            parts.append(line.strip())
    for line in bd.get("sublines") or []:
        if isinstance(line, str) and line.strip():
            parts.append(line.strip())
    if not parts:
        s = item.get("summary")
        if isinstance(s, str) and s.strip():
            return s.strip()[:1200]
    return " ".join(parts)[:1200] if parts else ""


def _comparison_readiness_normalized(item: Dict[str, Any]) -> str:
    r = item.get("readiness") if isinstance(item.get("readiness"), dict) else {}
    cr = r.get("comparison_readiness")
    if isinstance(cr, str) and cr.strip():
        return cr.strip()
    hint = str(item.get("comparison_readiness_hint") or "partial")
    if hint == "ready":
        return READINESS_COMPARISON_READY
    if hint == "external_reference":
        return READINESS_EXTERNAL_REFERENCE_PARTIAL
    if hint == "draft_only":
        return READINESS_REVIEW_REQUIRED
    if hint == "not_ready":
        return READINESS_REVIEW_REQUIRED
    return READINESS_REVIEW_REQUIRED


def _review_needed_for_item(item: Dict[str, Any], comparison_readiness: str) -> bool:
    if bool(item.get("draft_only_unresolved")):
        return True
    if comparison_readiness in (
        READINESS_REVIEW_REQUIRED,
        READINESS_EXTERNAL_REFERENCE_PARTIAL,
    ):
        return True
    if comparison_readiness == READINESS_INFORMATIONAL_ONLY:
        return False
    if comparison_readiness == READINESS_DETERMINISTIC_NON_BUDGET:
        return False
    return comparison_readiness != READINESS_COMPARISON_READY


def _confidence_for_grouped_item(
    item: Dict[str, Any],
    clauses: Sequence[Dict[str, Any]],
    drafts_by_clause: Dict[int, List[Dict[str, Any]]],
) -> Optional[float]:
    scores: List[float] = []
    for ci in item.get("source_clause_indices") or []:
        if not isinstance(ci, int):
            continue
        cl = clauses[ci] if 0 <= ci < len(clauses) else None
        if isinstance(cl, dict):
            try:
                v = float(cl.get("confidence") or 0)
                if v > 0:
                    scores.append(v)
            except (TypeError, ValueError):
                pass
        for d in drafts_by_clause.get(ci, []) or []:
            try:
                v = float(d.get("confidence") or 0)
                if v > 0:
                    scores.append(v)
            except (TypeError, ValueError):
                pass
    if not scores:
        return None
    return round(min(0.99, max(scores)), 4)


def _child_variants(item: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    bd = item.get("business_display") if isinstance(item.get("business_display"), dict) else {}
    out: List[Dict[str, Any]] = []
    for c in bd.get("variant_chips") or []:
        if isinstance(c, str) and c.strip():
            out.append({"kind": "variant", "label": c.strip()})
    for line in bd.get("tier_lines") or []:
        if isinstance(line, str) and line.strip():
            out.append({"kind": "amount_tier", "label": line.strip()})
    for line in bd.get("sublines") or []:
        if isinstance(line, str) and line.strip():
            out.append({"kind": "detail", "label": line.strip()})
    gv = item.get("grouped_values") if isinstance(item.get("grouped_values"), dict) else {}
    dd = gv.get("duration_days")
    if isinstance(dd, int) and dd > 0:
        out.append({"kind": "duration", "label": f"{dd} days", "duration_days": dd})
    return out or None


def _serialize_grouped_item_row(
    item: Dict[str, Any],
    clauses: Sequence[Dict[str, Any]],
    drafts_by_clause: Dict[int, List[Dict[str, Any]]],
    template_item_by_key: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    comparison_readiness = _comparison_readiness_normalized(item)
    ck = item.get("canonical_key")
    ti = template_item_by_key.get(str(ck)) if ck else None
    review_needed = _review_needed_for_item(item, comparison_readiness)
    if isinstance(ti, dict) and ti.get("review_needed") is True:
        review_needed = True

    excerpt = item.get("summary")
    if not isinstance(excerpt, str):
        excerpt = ""
    excerpt = excerpt.strip()[:2000]

    row: Dict[str, Any] = {
        "grouped_item_id": item.get("grouped_item_id"),
        "canonical_key": ck,
        "title": item.get("title"),
        "imported_value_summary": _imported_value_summary(item),
        "applicability_summary": _applicability_summary(item.get("applicability_dimensions") or []),
        "comparison_readiness": comparison_readiness,
        "comparison_readiness_reason": (
            (item.get("readiness") or {}).get("reason") if isinstance(item.get("readiness"), dict) else None
        ),
        "source_ref": item.get("source_ref"),
        "source_excerpt": excerpt,
        "confidence": _confidence_for_grouped_item(item, clauses, drafts_by_clause),
        "review_needed": review_needed,
        "coverage_status": item.get("coverage_status"),
        "merged_draft_candidate_count": item.get("merged_draft_candidate_count"),
        "source_clause_indices": item.get("source_clause_indices") or [],
    }
    cv = _child_variants(item)
    if cv:
        row["child_variants"] = cv
    return row


def _empty_slots_by_domain(
    template_first_import: Optional[Dict[str, Any]],
) -> Dict[str, List[str]]:
    """Map API domain key -> canonical keys still empty in template-first view."""
    out: Dict[str, List[str]] = {t[0]: [] for t in GROUPED_REVIEW_DOMAIN_DEFS}
    out["unmapped"] = []
    if not isinstance(template_first_import, dict):
        return out
    for it in template_first_import.get("template_items") or []:
        if not isinstance(it, dict):
            continue
        if it.get("import_status") != "unmapped":
            continue
        ck = it.get("canonical_key")
        if not isinstance(ck, str):
            continue
        dom = _api_domain_for_canonical_key(ck)
        out.setdefault(dom, []).append(ck)
    return out


def build_grouped_hr_review(
    grouped_policy_items: Sequence[Dict[str, Any]],
    clauses: Sequence[Dict[str, Any]],
    draft_rule_candidates: Sequence[Dict[str, Any]],
    template_first_import: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Primary HR-facing structure: template domains with collapsed rows.

    Draft rule candidates remain on the payload root for diagnostics.
    """
    clause_list = [c for c in clauses if isinstance(c, dict)]
    drafts_by = _drafts_by_clause_index(draft_rule_candidates)

    template_item_by_key: Dict[str, Dict[str, Any]] = {}
    if isinstance(template_first_import, dict):
        for it in template_first_import.get("template_items") or []:
            if isinstance(it, dict) and isinstance(it.get("canonical_key"), str):
                template_item_by_key[str(it["canonical_key"])] = it

    domain_items: Dict[str, List[Dict[str, Any]]] = {t[0]: [] for t in GROUPED_REVIEW_DOMAIN_DEFS}
    domain_items["unmapped"] = []

    for g in grouped_policy_items:
        if not isinstance(g, dict):
            continue
        dom = _api_domain_for_canonical_key(g.get("canonical_key"))
        domain_items.setdefault(dom, []).append(
            _serialize_grouped_item_row(g, clause_list, drafts_by, template_item_by_key)
        )

    template_domains: Dict[str, Any] = {}
    domain_order: List[str] = []
    for api_key, _tid, title in GROUPED_REVIEW_DOMAIN_DEFS:
        domain_order.append(api_key)
        template_domains[api_key] = {
            "domain_key": api_key,
            "template_domain_id": _tid,
            "domain_title": title,
            "items": domain_items.get(api_key) or [],
        }
    if domain_items.get("unmapped"):
        domain_order.append("unmapped")
        template_domains["unmapped"] = {
            "domain_key": "unmapped",
            "template_domain_id": None,
            "domain_title": "Needs template mapping",
            "items": domain_items["unmapped"],
        }

    imp = template_first_import.get("import_summary") if isinstance(template_first_import, dict) else {}
    imp = imp if isinstance(imp, dict) else {}

    mapped_n = int(imp.get("mapped_items_count") or 0)
    template_field_count = int(imp.get("template_field_count") or 0)
    still_empty = max(0, template_field_count - mapped_n) if template_field_count else 0
    review_n = int(imp.get("review_required_items_count") or 0)

    merged_extra = 0
    for g in grouped_policy_items:
        if not isinstance(g, dict):
            continue
        m = int(g.get("merged_draft_candidate_count") or 1)
        if m > 1:
            merged_extra += m - 1

    items_needing_review_rows = sum(
        1
        for dom in template_domains.values()
        for it in dom.get("items") or []
        if isinstance(it, dict) and it.get("review_needed")
    )

    empty_by_domain = _empty_slots_by_domain(template_first_import)

    return {
        "template_domains": template_domains,
        "domain_order": domain_order,
        "import_summary": {
            "mapped_items_count": mapped_n,
            "grouped_items_count": int(imp.get("grouped_items_count") or len(grouped_policy_items)),
            "unmapped_rows_count": int(imp.get("unmapped_rows_count") or 0),
            "template_field_count": template_field_count,
            "review_required_items_count": review_n,
        },
        "duplicate_merge_summary": {
            "duplicate_rows_merged_count": int(imp.get("duplicate_rows_merged_count") or 0),
            "grouped_policy_items_count": len([g for g in grouped_policy_items if isinstance(g, dict)]),
            "extra_drafts_merged_into_groups": merged_extra,
        },
        "counts": {
            "items_populated_from_upload": mapped_n,
            "items_still_empty_in_template": still_empty,
            "items_needing_review_grouped_rows": items_needing_review_rows,
            "items_needing_review_template_fields": review_n,
            "grouped_review_rows": len([g for g in grouped_policy_items if isinstance(g, dict)]),
            "draft_rule_candidates_count": len([d for d in draft_rule_candidates if isinstance(d, dict)]),
        },
        "items_needing_review": {
            "grouped_rows": items_needing_review_rows,
            "template_fields": review_n,
        },
        "empty_template_slots_by_domain": empty_by_domain,
    }
