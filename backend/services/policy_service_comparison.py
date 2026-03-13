"""
Service-policy comparison: evaluates selected employee services and answers
against the resolved assignment policy.

Produces comparison results usable in both employee read-only and HR review views.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .policy_taxonomy import get_benefit_meta

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

    approval = bool(benefit.get("approval_required", False))
    max_val = benefit.get("max_value")
    std_val = benefit.get("standard_value")
    min_val = benefit.get("min_value")
    currency = benefit.get("currency") or "USD"

    # Determine requested amount for comparison
    requested_amount = requested.get("requested_amount") or requested.get("requested_annual") or requested.get("estimated_cost")
    policy_cap = max_val if max_val is not None else std_val

    variance: Dict[str, Any] = {}

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
) -> Dict[str, Any]:
    """
    Compute comparison between selected services + answers and resolved policy.

    Returns structured result for employee (read-only) or HR (with diagnostics).
    """
    assignment = assignment or db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        return {"comparisons": [], "message": "Assignment not found.", "resolved_policy": None}

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
        return {
            "comparisons": [],
            "message": "No published policy for this assignment. Cannot compare services.",
            "resolved_policy": None,
        }

    benefits = db.list_resolved_policy_benefits(resolved["id"])
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
    if include_diagnostics:
        result["diagnostics"] = {
            "benefits_count": len(benefits),
            "services_count": len(case_services),
            "answers_keys": list(answers_flat.keys()),
        }
    return result
