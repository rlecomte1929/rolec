"""
Applicability evaluation for imported policy facts vs mobility case profile (deterministic).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set


def _lower_set(xs: Any) -> Set[str]:
    if not isinstance(xs, list):
        return set()
    return {str(x).strip().lower() for x in xs if str(x).strip()}


def evaluate_fact_applicability(
    fact: Dict[str, Any],
    case_profile: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Returns applicability_status, matched_conditions, conflicting_conditions, missing_case_fields.
    """
    app = fact.get("applicability_json") or {}
    if not isinstance(app, dict):
        app = {}

    missing: List[str] = []
    matched: List[str] = []
    conflicts: List[str] = []

    case_at = (case_profile.get("assignment_type") or "").strip().lower() or None
    req_at = _lower_set(app.get("assignment_types"))
    if req_at:
        if not case_at:
            missing.append("assignment_type")
        elif case_at not in req_at:
            return {
                "applicability_status": "not_applicable",
                "matched_conditions": [],
                "conflicting_conditions": [f"assignment_type:{case_at} not in {sorted(req_at)}"],
                "missing_case_fields": missing,
            }
        matched.append("assignment_type")

    fam = case_profile.get("family") or {}
    req_fs = _lower_set(app.get("family_statuses"))
    if req_fs:
        has_dep = bool(fam.get("has_dependents"))
        has_sp = bool(fam.get("has_accompanying_spouse"))
        if "with_children" in req_fs or "dependents" in req_fs:
            if not has_dep:
                missing.append("dependent_children_confirmed")
        if "married" in req_fs or "spouse" in req_fs:
            if not has_sp:
                missing.append("spouse_status")
        if app.get("dependent_children_required") and not has_dep:
            return {
                "applicability_status": "not_applicable",
                "matched_conditions": matched,
                "conflicting_conditions": ["dependent_children_required"],
                "missing_case_fields": missing,
            }

    dest = (case_profile.get("destination_country") or "").strip().upper()
    req_dc = {str(x).strip().upper() for x in (app.get("destination_countries") or []) if x}
    if req_dc and dest and dest not in req_dc:
        return {
            "applicability_status": "not_applicable",
            "matched_conditions": matched,
            "conflicting_conditions": [f"destination {dest} not in policy scope {sorted(req_dc)}"],
            "missing_case_fields": missing,
        }
    if req_dc and not dest:
        missing.append("destination_country")

    ori = (case_profile.get("origin_country") or "").strip().upper()
    req_oc = {str(x).strip().upper() for x in (app.get("origin_countries") or []) if x}
    if req_oc and ori and ori not in req_oc:
        return {
            "applicability_status": "not_applicable",
            "matched_conditions": matched,
            "conflicting_conditions": [f"origin {ori} not in {sorted(req_oc)}"],
            "missing_case_fields": missing,
        }

    req_levels = _lower_set(app.get("employee_levels"))
    meta = case_profile.get("metadata") or {}
    level = (meta.get("employee_level") or meta.get("job_level") or "").strip().lower()
    if req_levels:
        if not level:
            missing.append("employee_level")
        elif level not in req_levels:
            return {
                "applicability_status": "not_applicable",
                "matched_conditions": matched,
                "conflicting_conditions": [f"employee_level {level}"],
                "missing_case_fields": missing,
            }

    amb = bool(fact.get("ambiguity_flag"))
    quote = (fact.get("source_quote") or "").lower()
    soft_signals = ("may ", "typically", "subject to approval", "exceptional", "discretionary", "at hr", "case-by-case")
    soft = any(s in quote for s in soft_signals)

    if missing:
        return {
            "applicability_status": "cannot_determine_missing_case_data",
            "matched_conditions": matched,
            "conflicting_conditions": conflicts,
            "missing_case_fields": missing,
            "soft_language_detected": soft,
        }
    if amb or soft:
        return {
            "applicability_status": "cannot_determine_policy_ambiguity",
            "matched_conditions": matched,
            "conflicting_conditions": conflicts,
            "missing_case_fields": [],
            "soft_language_detected": soft,
        }
    return {
        "applicability_status": "applicable",
        "matched_conditions": matched,
        "conflicting_conditions": conflicts,
        "missing_case_fields": [],
    }


def detect_fact_conflicts(facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Surface conflicting caps/rules for the same fact_type + category from different chunks."""
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for f in facts:
        key = f"{f.get('fact_type')}:{f.get('category')}"
        buckets.setdefault(key, []).append(f)
    out: List[Dict[str, Any]] = []
    for k, group in buckets.items():
        if len(group) < 2:
            continue
        vals = [json.dumps(x.get("normalized_value_json") or {}, sort_keys=True, default=str) for x in group]
        if len(set(vals)) > 1:
            out.append({"bucket": k, "facts": [x.get("id") for x in group], "reason": "conflicting_normalized_values"})
    return out
