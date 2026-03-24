"""
Grouped business-facing policy items vs atomic comparison subrules.

HR review prefers one grouped item per logical benefit (canonical or service key cluster).
The comparison engine consumes optional atomic subrules derived from grouped values — not as the
primary HR structure.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .policy_canonical_lta_template import get_canonical_lta_field
from .policy_grouped_comparison_readiness import enrich_grouped_items_with_readiness
from .policy_lta_grouping_heuristics import merge_lta_pattern_dict

GROUPED_POLICY_MODEL_VERSION = 1


def _normalize_excerpt_fingerprint(text: str) -> str:
    s = (text or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s]", "", s)
    return s[:500]


def _merge_grouped_values(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if k not in out:
            out[k] = v
            continue
        if k == "notes" and isinstance(out[k], list) and isinstance(v, list):
            out[k] = sorted(set(out[k] + v))
        elif k == "conditions" and isinstance(out[k], list) and isinstance(v, list):
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
        elif k == "reimbursement_logic":
            if v == "difference_only" or out.get(k) == "difference_only":
                out[k] = "difference_only"
            else:
                out[k] = v or out.get(k)
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
        elif k == "external_governance" and isinstance(out[k], dict) and isinstance(v, dict):
            rp0 = out[k].get("reference_phrases") or []
            rp1 = v.get("reference_phrases") or []
            merged = {**out[k], **v}
            if isinstance(rp0, list) and isinstance(rp1, list):
                merged["reference_phrases"] = list(dict.fromkeys(rp0 + rp1))
            merged["is_externally_governed"] = bool(
                out[k].get("is_externally_governed") or v.get("is_externally_governed")
            )
            out[k] = merged
        elif k == "family_coverage" and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    return out


def _cluster_key(draft: Dict[str, Any], clause: Optional[Dict[str, Any]]) -> Tuple[str, ...]:
    hints = (clause or {}).get("normalized_hint_json") if clause else None
    if not isinstance(hints, dict):
        hints = {}
    m = hints.get("canonical_lta_row_mapping")
    if not isinstance(m, dict):
        m = {}
    trace = draft.get("source_trace") or {}
    if not isinstance(trace, dict):
        trace = {}
    section_ref = str(trace.get("section_ref") or "").strip()
    excerpt = (draft.get("source_excerpt") or "").strip()
    if m:
        pk = m.get("primary_canonical_key")
        fp = str(m.get("normalized_text_fingerprint") or "").strip()
        if not fp:
            fp = _normalize_excerpt_fingerprint(excerpt)
        canon = pk if pk else "__draft_unresolved__"
        return ("lta", str(canon), section_ref, fp)
    sk = draft.get("candidate_service_key")
    fp2 = _normalize_excerpt_fingerprint(excerpt)
    return ("benefit", str(sk or ""), section_ref, fp2)


def _stable_group_id(cluster_key: Tuple[str, ...]) -> str:
    raw = "|".join(cluster_key).encode("utf-8")
    h = hashlib.sha256(raw).hexdigest()[:20]
    return f"gpi-{h}"


def _title_for_cluster(
    canonical_key: Optional[str],
    service_key: Optional[str],
    first_clause_title: Optional[str],
) -> str:
    if canonical_key and canonical_key != "__draft_unresolved__":
        f = get_canonical_lta_field(canonical_key)
        if f:
            return f.employee_visible_label
    if service_key:
        return service_key.replace("_", " ").title()
    if first_clause_title:
        return str(first_clause_title)[:200]
    return "Policy item"


def _business_display(
    title: str,
    summary: str,
    grouped_values: Dict[str, Any],
    canonical_key: Optional[str],
) -> Dict[str, Any]:
    chips: List[str] = []
    tier_lines: List[str] = []
    for v in grouped_values.get("leave_variants") or []:
        if isinstance(v, str) and v.strip():
            chips.append(v.strip())
    for t in grouped_values.get("amount_tiers") or []:
        if not isinstance(t, dict):
            continue
        role = t.get("role", "tier")
        amt = t.get("amount_text", "")
        if amt:
            tier_lines.append(f"{role}: {amt}")
    sublines: List[str] = []
    if grouped_values.get("reimbursement_logic") == "difference_only":
        sublines.append("Reimbursement: fee difference / differential logic")
    if grouped_values.get("cap_basis") == "external_or_third_party":
        sublines.append("Cap or level may reference external or third-party data")
    if grouped_values.get("allowance_payment_type") == "one_off":
        sublines.append("Payment type: one-off / lump sum")
    if grouped_values.get("reimbursement_cap_mentioned"):
        sublines.append("Capped reimbursement or maximum referenced")
    eg = grouped_values.get("external_governance")
    if isinstance(eg, dict) and eg.get("is_externally_governed"):
        refs = eg.get("reference_phrases") or []
        if isinstance(refs, list) and refs:
            sublines.append(
                "Externally governed: " + "; ".join(str(x) for x in refs[:3])[:280]
            )
    for g in grouped_values.get("governance_conditions") or []:
        if isinstance(g, dict) and g.get("text"):
            sublines.append(str(g["text"])[:200])
    return {
        "headline": title,
        "summary_paragraph": summary[:2000],
        "variant_chips": chips[:24],
        "tier_lines": tier_lines[:12],
        "sublines": sublines,
        "primary_canonical_key": canonical_key,
    }


def build_grouped_policy_items(
    clauses: Sequence[Dict[str, Any]],
    draft_rule_candidates: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Cluster draft_rule_candidates so duplicate HR-facing rows (same LTA key + ref + text
    fingerprint, or same benefit + ref + excerpt fingerprint) collapse to one grouped item.
    """
    clause_list = [c for c in clauses if isinstance(c, dict)]
    by_idx = {i: clause_list[i] for i in range(len(clause_list))}

    buckets: Dict[Tuple[str, ...], List[Dict[str, Any]]] = {}
    order: List[Tuple[str, ...]] = []
    for draft in draft_rule_candidates:
        if not isinstance(draft, dict):
            continue
        idx = draft.get("clause_index")
        clause = by_idx.get(idx) if isinstance(idx, int) else None
        key = _cluster_key(draft, clause)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(draft)

    out: List[Dict[str, Any]] = []
    for key in order:
        group_drafts = buckets[key]
        first = group_drafts[0]
        idx0 = first.get("clause_index")
        clause0 = by_idx.get(idx0) if isinstance(idx0, int) else None
        hints0 = (clause0 or {}).get("normalized_hint_json") if clause0 else {}
        if not isinstance(hints0, dict):
            hints0 = {}
        m0 = hints0.get("canonical_lta_row_mapping")
        if not isinstance(m0, dict):
            m0 = {}

        canonical_key: Optional[str] = m0.get("primary_canonical_key")
        if canonical_key == "__draft_unresolved__":
            canonical_key = None
        draft_unresolved = bool(m0.get("draft_only_unresolved"))

        grouped_values: Dict[str, Any] = {}
        comparison_hint = str(m0.get("comparison_readiness_hint") or "partial")
        coverage_status = str(m0.get("coverage_status") or "mentioned")
        applicability: List[str] = []
        if isinstance(m0.get("applicability"), list):
            applicability = [str(x) for x in m0["applicability"]]

        for d in group_drafts:
            di = d.get("clause_index")
            cl = by_idx.get(di) if isinstance(di, int) else None
            h = (cl or {}).get("normalized_hint_json") if cl else {}
            if not isinstance(h, dict):
                h = {}
            mm = h.get("canonical_lta_row_mapping")
            if isinstance(mm, dict) and isinstance(mm.get("sub_values"), dict):
                grouped_values = _merge_grouped_values(grouped_values, mm["sub_values"])

        excerpts: List[str] = []
        for d in group_drafts:
            ex = (d.get("source_excerpt") or "").strip()
            if ex and ex not in excerpts:
                excerpts.append(ex)
        summary = "\n\n".join(excerpts) if len(excerpts) > 1 else (excerpts[0] if excerpts else "")

        trace0 = first.get("source_trace") or {}
        source_ref = str(trace0.get("section_ref") or "").strip() or None
        if not source_ref and isinstance(m0.get("provenance"), dict):
            source_ref = m0["provenance"].get("section_reference")

        clause_title = (clause0 or {}).get("title") if clause0 else None
        service_key = first.get("candidate_service_key")
        title = _title_for_cluster(canonical_key, service_key, clause_title)

        explicit_numeric_cap = any(
            (d.get("amount_fragments") or {}).get("amount_value") is not None for d in group_drafts
        )
        for d in group_drafts:
            nums = (d.get("amount_fragments") or {}).get("numeric_values_hint") or []
            if isinstance(nums, list) and len(nums) > 0:
                explicit_numeric_cap = True

        gid = _stable_group_id(key)
        out.append(
            {
                "schema_version": GROUPED_POLICY_MODEL_VERSION,
                "grouped_item_id": gid,
                "canonical_key": canonical_key,
                "taxonomy_service_key": service_key if isinstance(service_key, str) else None,
                "title": title,
                "summary": summary[:4000],
                "source_ref": source_ref,
                "grouped_values": grouped_values,
                "business_display": _business_display(title, summary, grouped_values, canonical_key),
                "comparison_readiness_hint": comparison_hint,
                "coverage_status": coverage_status,
                "applicability_dimensions": applicability,
                "draft_only_unresolved": draft_unresolved,
                "explicit_numeric_cap": explicit_numeric_cap,
                "source_clause_indices": sorted(
                    {int(d["clause_index"]) for d in group_drafts if isinstance(d.get("clause_index"), int)}
                ),
                "merged_draft_candidate_count": len(group_drafts),
            }
        )
    return out


def derive_comparison_subrules_from_grouped_item(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Atomic subrules for engines — amounts/durations/applicability when structurally available.
    Host housing with external cap and no explicit amount yields a non-comparable stub only.
    """
    gid = str(item.get("grouped_item_id") or "unknown")
    key = item.get("canonical_key")
    gv = item.get("grouped_values") if isinstance(item.get("grouped_values"), dict) else {}
    explicit_cap = bool(item.get("explicit_numeric_cap"))
    subrules: List[Dict[str, Any]] = []

    if key == "relocation_allowance":
        for t in gv.get("amount_tiers") or []:
            if not isinstance(t, dict):
                continue
            role = str(t.get("role", "tier"))
            amt_txt = t.get("amount_text")
            val: Optional[float] = None
            if amt_txt is not None:
                try:
                    val = float(str(amt_txt).replace(",", ""))
                except (TypeError, ValueError):
                    val = None
            subrules.append(
                {
                    "subrule_id": f"{gid}-amt-{role}",
                    "parent_grouped_item_id": gid,
                    "kind": "amount_tier",
                    "compare_eligible": val is not None and val > 0,
                    "employee_tier_applicability": role,
                    "family_applicability": [],
                    "amount_value": val,
                    "currency": None,
                    "duration_days": None,
                    "variant_label": None,
                    "notes": None,
                }
            )
        return subrules

    if key == "home_leave":
        variants = gv.get("leave_variants") or []
        if isinstance(variants, list) and variants:
            for i, v in enumerate(variants):
                if not isinstance(v, str):
                    continue
                subrules.append(
                    {
                        "subrule_id": f"{gid}-var-{i}",
                        "parent_grouped_item_id": gid,
                        "kind": "travel_variant",
                        "compare_eligible": False,
                        "employee_tier_applicability": None,
                        "family_applicability": [],
                        "amount_value": None,
                        "currency": None,
                        "duration_days": None,
                        "variant_label": v.strip()[:500],
                        "notes": "Narrative variant; no automatic numeric compare",
                    }
                )
        return subrules

    if key == "child_education":
        subrules.append(
            {
                "subrule_id": f"{gid}-edu-cond",
                "parent_grouped_item_id": gid,
                "kind": "education_condition",
                "compare_eligible": False,
                "employee_tier_applicability": None,
                "family_applicability": ["children"],
                "amount_value": None,
                "currency": None,
                "duration_days": None,
                "variant_label": None,
                "notes": "Conditions / eligibility captured at grouped level",
            }
        )
        if gv.get("reimbursement_logic") == "difference_only":
            subrules.append(
                {
                    "subrule_id": f"{gid}-edu-diff",
                    "parent_grouped_item_id": gid,
                    "kind": "reimbursement_differential",
                    "compare_eligible": True,
                    "employee_tier_applicability": None,
                    "family_applicability": ["children"],
                    "amount_value": None,
                    "currency": None,
                    "duration_days": None,
                    "variant_label": None,
                    "notes": "difference_only — compare structure, not a single cap",
                }
            )
        return subrules

    if key == "host_housing":
        if gv.get("cap_basis") == "external_or_third_party" or item.get("comparison_readiness_hint") == "external_reference":
            if explicit_cap:
                subrules.append(
                    {
                        "subrule_id": f"{gid}-hs-cap",
                        "parent_grouped_item_id": gid,
                        "kind": "housing_cap",
                        "compare_eligible": True,
                        "employee_tier_applicability": None,
                        "family_applicability": [],
                        "amount_value": None,
                        "currency": None,
                        "duration_days": None,
                        "variant_label": None,
                        "notes": "Explicit cap present in extraction hints",
                    }
                )
            else:
                subrules.append(
                    {
                        "subrule_id": f"{gid}-hs-ext",
                        "parent_grouped_item_id": gid,
                        "kind": "external_reference",
                        "compare_eligible": False,
                        "employee_tier_applicability": None,
                        "family_applicability": [],
                        "amount_value": None,
                        "currency": None,
                        "duration_days": None,
                        "variant_label": None,
                        "notes": "No atomic budget compare unless cap is explicit in policy text",
                    }
                )
        return subrules

    if key == "temporary_living_outbound":
        dur = gv.get("duration_days")
        if isinstance(dur, int) and dur > 0:
            subrules.append(
                {
                    "subrule_id": f"{gid}-tl-dur",
                    "parent_grouped_item_id": gid,
                    "kind": "duration_cap",
                    "compare_eligible": True,
                    "employee_tier_applicability": None,
                    "family_applicability": [],
                    "amount_value": None,
                    "currency": None,
                    "duration_days": dur,
                    "variant_label": None,
                    "notes": None,
                }
            )
        return subrules

    return subrules


def build_comparison_subrules_for_grouped_items(
    grouped_items: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Flatten atomic comparison subrules from grouped items (grouped_values must already be merged)."""
    all_sub: List[Dict[str, Any]] = []
    for item in grouped_items:
        if isinstance(item, dict):
            all_sub.extend(derive_comparison_subrules_from_grouped_item(item))
    return all_sub


def build_grouped_policy_review_view(
    clauses: Sequence[Dict[str, Any]],
    draft_rule_candidates: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    grouped = build_grouped_policy_items(clauses, draft_rule_candidates)
    # Merge quantification.duration_days into grouped_values for temp living before subrule derive
    clause_list = [c for c in clauses if isinstance(c, dict)]
    by_idx = {i: clause_list[i] for i in range(len(clause_list))}
    cluster_drafts: Dict[str, List[Dict[str, Any]]] = {}
    for draft in draft_rule_candidates:
        if not isinstance(draft, dict):
            continue
        idx = draft.get("clause_index")
        cl = by_idx.get(idx) if isinstance(idx, int) else None
        gid = _stable_group_id(_cluster_key(draft, cl))
        cluster_drafts.setdefault(gid, []).append(draft)
    for g in grouped:
        gid = str(g.get("grouped_item_id") or "")
        for d in cluster_drafts.get(gid, []):
            di = d.get("clause_index")
            cl = by_idx.get(di) if isinstance(di, int) else None
            h = (cl or {}).get("normalized_hint_json") if cl else {}
            if not isinstance(h, dict):
                continue
            m = h.get("canonical_lta_row_mapping")
            if not isinstance(m, dict):
                continue
            q = m.get("quantification")
            if isinstance(q, dict) and q.get("duration_days"):
                gv = g.get("grouped_values")
                if not isinstance(gv, dict):
                    gv = {}
                else:
                    gv = dict(gv)
                gv["duration_days"] = q["duration_days"]
                g["grouped_values"] = gv
                break

    enrich_grouped_items_with_readiness(grouped, cluster_drafts)
    subrules = build_comparison_subrules_for_grouped_items(grouped)
    return grouped, subrules


def grouped_items_to_atomic_comparison_subrules(
    grouped_items: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Engine-oriented alias: expand grouped items into atomic comparison subrules."""
    return build_comparison_subrules_for_grouped_items(grouped_items)
