"""
Canonical recommendation input builder.

Single source of truth for compiling recommendation criteria from:
- assignment_id, case_id, canonical_case_id
- selected services
- saved dynamic answers
- destination country/city
- household/family context
- company policy/budget context (when available)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Service key (frontend) -> backend category key
SERVICE_KEY_TO_BACKEND: Dict[str, str] = {
    "housing": "living_areas",
    "schools": "schools",
    "movers": "movers",
    "banks": "banks",
    "insurances": "insurance",
    "electricity": "electricity",
}


def _flatten_saved_answers(answers_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge all saved answers by service into one flat dict (last wins)."""
    flat: Dict[str, Any] = {}
    for row in answers_rows:
        ans = row.get("answers") or {}
        if isinstance(ans, str):
            try:
                ans = json.loads(ans)
            except Exception:
                ans = {}
        for k, v in ans.items():
            if v is not None:
                flat[k] = v
    return flat


def _apply_service_shaping(
    service_key: str,
    criteria: Dict[str, Any],
) -> Dict[str, Any]:
    """Apply plugin-specific shaping. Replaces frontend buildCriteriaForService."""
    out = dict(criteria)

    if service_key == "housing":
        min_b = out.get("budget_min")
        max_b = out.get("budget_max")
        min_val = int(min_b) if isinstance(min_b, (int, float)) else 2000
        max_val = int(max_b) if isinstance(max_b, (int, float)) else 5000
        out["budget_monthly"] = {"min": min_val, "max": max_val}
        commute = out.get("commute_mins")
        if isinstance(commute, (int, float)):
            out["commute_work"] = {
                "max_minutes": int(commute),
                "address": out.get("office_address") or "",
                "mode": "transit",
            }
        for k in ("budget_min", "budget_max", "commute_mins"):
            out.pop(k, None)

    elif service_key == "schools":
        child_ages = out.get("child_ages")
        if isinstance(child_ages, str):
            ages = [
                int(x.strip())
                for x in child_ages.split(",")
                if x.strip() and x.strip().isdigit()
            ]
            out["child_ages"] = ages if ages else [8]
        elif isinstance(child_ages, list):
            out["child_ages"] = [int(x) for x in child_ages if isinstance(x, (int, float))]

    elif service_key == "banks":
        pl = out.get("preferred_languages")
        if isinstance(pl, str):
            out["preferred_languages"] = [pl]
        if not isinstance(out.get("preferred_languages"), list):
            out["preferred_languages"] = ["en"]

    elif service_key == "movers":
        acc_type = out.get("acc_type") or "apartment"
        bedrooms = out.get("acc_bedrooms")
        bed_val = int(bedrooms) if isinstance(bedrooms, (int, float)) else 2
        out["current_accommodation"] = {
            "type": acc_type,
            "bedrooms": bed_val,
            "sqm": 80,
        }
        for k in ("acc_type", "acc_bedrooms"):
            out.pop(k, None)

    elif service_key == "insurances":
        cov = out.get("coverage_types")
        if isinstance(cov, str):
            cov_list = [
                s.strip().lower()
                for s in cov.split(",")
                if s.strip()
            ]
            out["coverage_types"] = cov_list if cov_list else ["health"]
        elif not isinstance(out.get("coverage_types"), list):
            out["coverage_types"] = ["health"]

    return out


def build_criteria_for_assignment(
    assignment_id: str,
    case_id: str,
    selected_services: List[str],
    saved_answers: Dict[str, Any],
    case_context: Dict[str, Any],
    policy_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Build recommendation criteria for each selected service.

    Args:
        assignment_id: Assignment id
        case_id: Case id
        selected_services: List of service keys (housing, schools, movers, banks, insurances, electricity)
        saved_answers: Flattened answers from case_service_answers
        case_context: { destCity, destCountry, originCity, originCountry, dependents_ages, ... }
        policy_context: { currency, caps: { housing, moving, schools }, total_cap }

    Returns:
        Dict mapping backend_key -> criteria dict for that category
    """
    dest_city = (case_context.get("destCity") or case_context.get("destCountry") or "").strip()
    dest_country = (case_context.get("destCountry") or "").strip()
    origin_city = (case_context.get("originCity") or case_context.get("originCountry") or "").strip()

    # Question key -> criteria_key mapping (from question_schema.ServiceQuestionDef)
    CRITERIA_MAP: Dict[str, str] = {
        "budget_min": "budget_min",
        "budget_max": "budget_max",
        "bedrooms": "bedrooms",
        "sqm_min": "sqm_min",
        "commute_mins": "commute_mins",
        "office_address": "office_address",
        "child_ages": "child_ages",
        "school_type": "school_type",
        "curriculum": "curriculum",
        "school_budget": "budget_level",
        "origin_city": "origin_city",
        "move_type": "move_type",
        "acc_type": "acc_type",
        "acc_bedrooms": "acc_bedrooms",
        "people": "people",
        "packing": "packing_service",
        "bank_lang": "preferred_languages",
        "bank_fees": "fee_sensitivity",
        "ins_coverage": "coverage_types",
        "ins_family": "family_coverage",
        "elec_green": "green_preference",
        "elec_flex": "contract_flexibility",
    }
    result: Dict[str, Dict[str, Any]] = {}

    for svc_key in selected_services:
        backend_key = SERVICE_KEY_TO_BACKEND.get(svc_key)
        if not backend_key:
            continue

        criteria: Dict[str, Any] = {
            "assignment_id": assignment_id,
            "case_id": case_id,
            "destination_city": dest_city or "",
            "destination_country": dest_country or "",
        }
        if origin_city:
            criteria["origin_city"] = origin_city

        # Map saved answers to criteria
        for qkey, ckey in CRITERIA_MAP.items():
            if qkey in saved_answers:
                criteria[ckey] = saved_answers[qkey]

        # Prefill origin from case for movers
        if svc_key == "movers" and not criteria.get("origin_city") and origin_city:
            criteria["origin_city"] = origin_city

        # Policy context (budget caps for ranking/explainability)
        if policy_context:
            caps = policy_context.get("caps") or {}
            currency = policy_context.get("currency") or "USD"
            criteria["_policy_currency"] = currency
            if svc_key == "housing":
                cap = caps.get("housing")
                if cap is not None:
                    criteria["_policy_cap_monthly"] = float(cap)
            elif svc_key == "schools":
                cap = caps.get("schools")
                if cap is not None:
                    criteria["_policy_cap_annual"] = float(cap)
            elif svc_key == "movers":
                cap = caps.get("moving") or caps.get("movers")
                if cap is not None:
                    criteria["_policy_cap_one_time"] = float(cap)

        criteria = _apply_service_shaping(svc_key, criteria)
        result[backend_key] = criteria

    return result
