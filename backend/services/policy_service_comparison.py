"""
Service-policy comparison: evaluates selected employee services and answers
against the resolved assignment policy.

**Layer 2 only:** Uses `resolved_assignment_policy_*` / benefits keyed by `benefit_key`.
Never use `extracted_metadata` or document-level `mentioned_*` lists for comparison logic.

Employee calls use `employee_gate=True`: legacy ``comparisons`` are omitted unless
``evaluate_version_comparison_readiness`` is satisfied, but ``effective_service_comparison``
still runs (excluded / informational / not_enough_policy_data remain truthful; numeric
within/exceed is withheld when the version or rule is not comparison-ready).
HR calls omit the gate so HR can always inspect diagnostics.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .policy_taxonomy import get_benefit_meta
from .service_comparison_engine import (
    build_entitlements_by_benefit_key,
    compare_selected_services_effective_entitlements,
    map_case_service_to_canonical_selection,
)

log = logging.getLogger(__name__)

# Service category (case_services / question_schema) -> canonical benefit_key (policy taxonomy)
SERVICE_TO_BENEFIT: Dict[str, str] = {
    "housing": "temporary_housing",
    "living_areas": "temporary_housing",  # frontend backendKey for housing
    "schools": "schooling",
    "movers": "shipment",
    "banks": "banking_setup",
    "insurances": "insurance",
    "insurance": "insurance",
    "electricity": "out_of_scope",  # no direct policy mapping
}

# Budget level (school_budget answer) -> approximate annual USD for comparison
SCHOOL_BUDGET_LEVELS: Dict[str, int] = {
    "low": 15000,
    "medium": 25000,
    "high": 40000,
}


def _map_service_to_benefit(service_category: str) -> Optional[str]:
    """Map service category to canonical benefit key. Returns None for out_of_scope."""
    key = (service_category or "").lower().strip()
    benefit = SERVICE_TO_BENEFIT.get(key)
    if benefit == "out_of_scope":
        return None
    return benefit or None


def _extract_requested_values(
    service_category: str,
    answers: Dict[str, Any],
    case_service: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Extract requested values from service answers and case_services for comparison."""
    requested: Dict[str, Any] = {}
    cat = (service_category or "").lower()

    # Estimated cost from case_services
    if case_service:
        est = case_service.get("estimated_cost")
        if est is not None:
            requested["estimated_cost"] = float(est) if isinstance(est, (int, float)) else None
        requested["currency"] = case_service.get("currency") or "USD"
        requested["selected"] = bool(case_service.get("selected", True))

    if not answers:
        return requested

    if cat in ("housing", "living_areas"):
        budget_min = answers.get("budget_min") or answers.get("budget_max")
        budget_max = answers.get("budget_max") or answers.get("budget_min")
        if budget_min is not None:
            requested["budget_min_monthly"] = float(budget_min)
        if budget_max is not None:
            requested["budget_max_monthly"] = float(budget_max)
        if requested.get("budget_max_monthly"):
            requested["requested_annual"] = requested["budget_max_monthly"] * 12

    elif cat == "schools":
        level = (answers.get("school_budget") or "medium").lower()
        requested["school_budget_level"] = level
        requested["requested_annual"] = SCHOOL_BUDGET_LEVELS.get(level, 25000)
        requested["curriculum"] = answers.get("curriculum")
        requested["school_type"] = answers.get("school_type")

    elif cat == "movers":
        requested["move_type"] = answers.get("move_type")
        requested["packing"] = answers.get("packing")
        requested["people"] = answers.get("people")
        requested["acc_bedrooms"] = answers.get("acc_bedrooms")
        # Use estimated_cost if present
        if case_service and case_service.get("estimated_cost") is not None:
            requested["requested_amount"] = float(case_service["estimated_cost"])

    elif cat == "banks":
        requested["bank_lang"] = answers.get("bank_lang")
        requested["bank_fees"] = answers.get("bank_fees")

    elif cat == "insurances":
        requested["ins_type"] = answers.get("ins_type")
        requested["ins_family"] = answers.get("ins_family")

    return requested


def _compare_single(
    service_category: str,
    requested: Dict[str, Any],
    benefit: Optional[Dict[str, Any]],
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Compare requested values against policy benefit.
    Returns (policy_status, explanation, variance_json).
    """
    if benefit is None:
        if service_category.lower() == "electricity":
            return ("out_of_scope", "Electricity setup is not covered by relocation policy.", {})
        return ("out_of_scope", f"No policy rule for {service_category}.", {})

    included = bool(benefit.get("included", True))
    if not included:
        return (
            "excluded",
            benefit.get("condition_summary") or "This benefit is excluded by policy.",
            {},
        )

    cr = benefit.get("rule_comparison_readiness") if isinstance(benefit.get("rule_comparison_readiness"), dict) else {}
    cr_level = cr.get("level")

    approval = bool(benefit.get("approval_required", False))
    max_val = benefit.get("max_value")
    std_val = benefit.get("standard_value")
    min_val = benefit.get("min_value")
    currency = benefit.get("currency") or "USD"

    # Determine requested amount for comparison
    requested_amount = requested.get("requested_amount") or requested.get("requested_annual") or requested.get("estimated_cost")
    policy_cap = max_val if max_val is not None else std_val

    variance: Dict[str, Any] = {}

    if (
        cr_level == "not_ready"
        and requested_amount is None
        and policy_cap is None
    ):
        return (
            "uncertain",
            "Policy wording is too ambiguous for automated comparison; confirm limits with HR.",
            variance,
        )
    if (
        cr_level == "partial"
        and policy_cap is None
        and requested_amount is None
    ):
        return (
            "informational",
            "Included under policy; numeric comparison is not available (coverage-only or non-cap rule).",
            variance,
        )

    if requested_amount is not None and policy_cap is not None:
        try:
            req = float(requested_amount)
            cap = float(policy_cap)
            variance["requested"] = req
            variance["policy_limit"] = cap
            if req > cap:
                variance["over_by"] = req - cap
                if approval:
                    return (
                        "approval_required",
                        f"Requested {currency} {req:,.0f} exceeds policy cap of {currency} {cap:,.0f}. Pre-approval required.",
                        variance,
                    )
                return (
                    "capped",
                    f"Requested {currency} {req:,.0f} exceeds policy cap of {currency} {cap:,.0f}. Coverage limited to policy maximum.",
                    variance,
                )
        except (TypeError, ValueError):
            pass

    # Within limits
    if approval:
        return (
            "approval_required",
            benefit.get("condition_summary") or "Pre-approval required before proceeding.",
            variance,
        )

    # Partial: e.g. schooling differential-only, insurance type restrictions
    partial_reasons = []
    if service_category.lower() == "schools" and benefit.get("condition_summary", "").lower().find("differential") >= 0:
        partial_reasons.append("Policy covers differential only (local vs international school cost).")
    if service_category.lower() == "insurances":
        ins_type = requested.get("ins_type")
        if ins_type and ins_type not in ("health", "travel"):
            partial_reasons.append(f"Policy may not cover {ins_type} insurance. Verify with HR.")

    if partial_reasons:
        return ("partial", " ".join(partial_reasons), variance)

    return (
        "included",
        benefit.get("condition_summary") or f"Covered within policy limits ({currency} {policy_cap or '—'}).",
        variance,
    )


def compute_policy_service_comparison(
    db: Any,
    assignment_id: str,
    assignment: Optional[Dict[str, Any]] = None,
    include_diagnostics: bool = False,
    *,
    employee_gate: bool = False,
    selected_services_override: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Compute comparison between selected services + answers and resolved policy.

    Returns structured result for employee (read-only) or HR (with diagnostics).
    """
    assignment = assignment or db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        out: Dict[str, Any] = {
            "comparisons": [],
            "message": "Assignment not found.",
            "resolved_policy": None,
            "effective_service_comparison": [],
        }
        if employee_gate:
            out["comparison_available"] = False
        return out

    case_id = assignment.get("case_id")
    canonical_case_id = assignment.get("canonical_case_id") or case_id
    effective_case_id = db.coalesce_case_lookup_id(case_id) if case_id else None

    # Resolve policy if needed
    resolved = db.get_resolved_assignment_policy(assignment_id)
    if not resolved:
        from .policy_resolution import resolve_policy_for_assignment
        case = db.get_relocation_case(case_id) if case_id else None
        profile = None
        if case and case.get("profile_json"):
            try:
                import json
                profile = json.loads(case["profile_json"]) if isinstance(case["profile_json"], str) else case["profile_json"]
            except Exception:
                profile = None
        employee_profile = db.get_employee_profile(assignment_id)
        resolved = resolve_policy_for_assignment(db, assignment_id, assignment, case, profile, employee_profile)

    if not resolved:
        out = {
            "comparisons": [],
            "message": "No published policy for this assignment. Cannot compare services.",
            "resolved_policy": None,
            "effective_service_comparison": [],
        }
        if employee_gate:
            out["comparison_available"] = False
        return out

    comparison_readiness = None
    legacy_comparisons_suppressed = False
    if employee_gate:
        from .policy_comparison_readiness import evaluate_version_comparison_readiness

        pvid = resolved.get("policy_version_id")
        comparison_readiness = evaluate_version_comparison_readiness(db, str(pvid) if pvid else None)
        if not comparison_readiness.get("comparison_ready"):
            legacy_comparisons_suppressed = True

    benefits = db.list_resolved_policy_benefits(resolved["id"])
    pvid = resolved.get("policy_version_id")
    if pvid:
        from .policy_rule_comparison_readiness import enrich_resolved_benefits_with_rule_comparison

        benefits = enrich_resolved_benefits_with_rule_comparison(db, str(pvid), benefits)
    benefits_by_key: Dict[str, Dict] = {b.get("benefit_key"): b for b in benefits if b.get("benefit_key")}

    # Selected services and answers
    case_services = db.list_case_services(assignment_id)
    answers_rows = db.list_case_service_answers(effective_case_id) if effective_case_id else []

    answers_flat: Dict[str, Any] = {}
    for row in answers_rows:
        ans = row.get("answers") or {}
        if isinstance(ans, str):
            try:
                import json
                ans = json.loads(ans)
            except Exception:
                ans = {}
        for k, v in ans.items():
            if v is not None:
                answers_flat[k] = v

    # Group case_services by category (service_key often equals category)
    services_by_cat: Dict[str, Dict] = {}
    for s in case_services:
        if not s.get("selected", True):
            continue
        key = (s.get("category") or s.get("service_key") or "").lower()
        if not key:
            continue
        # Merge if multiple entries per category (take first with estimated_cost)
        if key not in services_by_cat or (s.get("estimated_cost") is not None and services_by_cat[key].get("estimated_cost") is None):
            services_by_cat[key] = s

    comparisons: List[Dict[str, Any]] = []
    seen_cats: set = set()

    if not legacy_comparisons_suppressed:
        for cat, case_svc in services_by_cat.items():
            if cat in seen_cats:
                continue
            seen_cats.add(cat)
            benefit_key = _map_service_to_benefit(cat)
            requested = _extract_requested_values(cat, answers_flat, case_svc)
            benefit = benefits_by_key.get(benefit_key) if benefit_key else None

            status, explanation, variance = _compare_single(cat, requested, benefit)

            meta = get_benefit_meta(benefit_key or cat)
            label = (meta.get("keywords") or [cat.replace("_", " ")])[0].replace("_", " ").title()

            rec: Dict[str, Any] = {
                "service_category": cat,
                "benefit_key": benefit_key or "out_of_scope",
                "label": label,
                "requested_value_json": requested,
                "policy_status": status,
                "explanation": explanation,
                "variance_json": variance,
                "approval_required": bool(benefit.get("approval_required")) if benefit else False,
                "evidence_required_json": list(benefit.get("evidence_required_json") or []) if benefit else [],
                "source_rule_ids_json": list(benefit.get("source_rule_ids_json") or []) if benefit else [],
            }
            if benefit:
                rec["policy_min_value"] = benefit.get("min_value")
                rec["policy_standard_value"] = benefit.get("standard_value")
                rec["policy_max_value"] = benefit.get("max_value")
                rec["currency"] = benefit.get("currency") or "USD"
                rec["amount_unit"] = benefit.get("amount_unit")
                if isinstance(benefit.get("rule_comparison_readiness"), dict):
                    rec["rule_comparison_readiness"] = benefit["rule_comparison_readiness"]
            else:
                rec["currency"] = requested.get("currency") or "USD"

            comparisons.append(rec)

    result: Dict[str, Any] = {
        "comparisons": comparisons,
        "resolved_policy": {
            "id": resolved.get("id"),
            "policy_version_id": resolved.get("policy_version_id"),
            "resolved_at": resolved.get("resolved_at"),
        },
        "assignment_id": assignment_id,
        "case_id": case_id,
        "canonical_case_id": canonical_case_id,
    }
    if employee_gate:
        result["comparison_available"] = not legacy_comparisons_suppressed
        if comparison_readiness is not None:
            result["comparison_readiness"] = comparison_readiness
        if legacy_comparisons_suppressed:
            result["message"] = (
                "Policy comparison is not available yet. You can still review service costs; "
                "company coverage and limits will appear here after your policy is published in a comparison-ready form."
            )
    if include_diagnostics:
        result["diagnostics"] = {
            "benefits_count": len(benefits),
            "services_count": len(case_services),
            "answers_keys": list(answers_flat.keys()),
        }

    # Effective-entitlement comparison engine (canonical service_key slice; rule_comparison_readiness-aware)
    version_ready = True
    if employee_gate and comparison_readiness is not None:
        version_ready = bool(comparison_readiness.get("comparison_ready"))
    engine_selections: List[Dict[str, Any]] = []
    if selected_services_override is not None:
        engine_selections = list(selected_services_override)
    else:
        for s in case_services:
            if not s.get("selected", True):
                continue
            mapped = map_case_service_to_canonical_selection(s)
            if mapped:
                engine_selections.append(mapped)
    by_sk: Dict[str, Dict[str, Any]] = {}
    for m in engine_selections:
        sk = m["service_key"]
        prev = by_sk.get(sk)
        if prev is None:
            by_sk[sk] = m
            continue
        if m.get("estimated_cost") is not None and prev.get("estimated_cost") is None:
            by_sk[sk] = m
    ent_by_bk = build_entitlements_by_benefit_key(benefits)
    result["effective_service_comparison"] = compare_selected_services_effective_entitlements(
        selected_services=list(by_sk.values()),
        entitlements_by_benefit_key=ent_by_bk,
        version_comparison_ready=version_ready,
    )
    return result
