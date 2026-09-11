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

from . import geo

log = logging.getLogger(__name__)

# Service key (frontend) -> primary backend category key
SERVICE_KEY_TO_BACKEND: Dict[str, str] = {
    "housing": "living_areas",
    "schools": "schools",
    "movers": "movers",
    "banks": "banks",
    "insurances": "insurance",
    "electricity": "electricity",
    "pets": "pets",
    "spouse": "partner_career",
}

# A frontend service can fan out to more than one backend category. "Housing" surfaces
# BOTH the advisory neighbourhood overview (living_areas) AND the gated housing agencies
# (housing_agencies) — two surfaces under one Housing step. Extra keys are ADDED to the
# primary from SERVICE_KEY_TO_BACKEND.
EXTRA_BACKENDS_FOR_SERVICE: Dict[str, List[str]] = {
    "housing": ["housing_agencies"],
}


def backends_for_service(service_key: str) -> List[str]:
    """All backend category keys a frontend service maps to (primary first)."""
    primary = SERVICE_KEY_TO_BACKEND.get(service_key)
    if not primary:
        return []
    return [primary, *EXTRA_BACKENDS_FOR_SERVICE.get(service_key, [])]


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
        mode = out.get("commute_mode") if out.get("commute_mode") in ("transit", "walk", "bike", "car") else "transit"
        if isinstance(commute, (int, float)):
            out["commute_work"] = {
                "max_minutes": int(commute),
                "address": out.get("office_address") or "",
                "mode": mode,
            }
        # Lifestyle multiselect -> priorities dict the living_areas scorer reads:
        # selected dimensions weight high (9), the rest stay neutral (5).
        lifestyle = out.get("housing_lifestyle")
        if isinstance(lifestyle, str):
            lifestyle = [s.strip() for s in lifestyle.split(",") if s.strip()]
        if isinstance(lifestyle, list) and lifestyle:
            selected = {str(x).strip().lower() for x in lifestyle}
            out["lifestyle_priorities"] = {
                k: (9 if k in selected else 5) for k in ("safety", "quiet", "green", "nightlife")
            }
        # Sub-type preference flows to the housing_agencies plugin (the living_areas
        # plugin ignores it) via the "housing" -> housing_agencies criteria fan-out.
        subtype = (out.get("housing_subtype") or "").strip().lower()
        if subtype in ("temporary", "permanent"):
            out["subtype_preference"] = subtype
        # Preferred / avoid neighbourhood names (free text -> list).
        for key in ("preferred_areas", "avoid_areas"):
            val = out.get(key)
            if isinstance(val, str):
                out[key] = [s.strip() for s in val.split(",") if s.strip()]
            elif not isinstance(val, list):
                out.pop(key, None)
        for k in ("budget_min", "budget_max", "commute_mins", "commute_mode", "housing_lifestyle", "housing_subtype"):
            out.pop(k, None)
        # Phase 1: geocode the office once (cached) so the plugin computes real
        # commute from coordinates. Best-effort — silent on failure/offline.
        office_addr = out.get("office_address")
        if office_addr:
            coord = geo.geocode(office_addr)
            if coord:
                out["office_lat"], out["office_lng"] = coord[0], coord[1]

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
        ins_type = (out.get("insurance_type") or "").strip().lower()
        cov = out.get("coverage_types")
        if isinstance(cov, str):
            cov_list = [s.strip().lower() for s in cov.split(",") if s.strip()]
        elif isinstance(cov, list):
            cov_list = [str(x).strip().lower() for x in cov if x]
        else:
            cov_list = []
        if ins_type and ins_type not in cov_list:
            cov_list.insert(0, ins_type)
        out["coverage_types"] = cov_list if cov_list else ["health"]
        out.pop("insurance_type", None)

    elif service_key == "spouse":
        spouse = out.pop("_spouse", None) or {}
        if isinstance(spouse, dict):
            emp = spouse.get("employment")
            if emp:
                out["employment"] = emp
            lang = spouse.get("languageLevel") or spouse.get("language_level")
            if lang:
                out["language_level"] = lang
            if "wantsToWork" in spouse:
                out["wants_to_work"] = spouse.get("wantsToWork")

    return out


def build_criteria_for_assignment(
    assignment_id: str,
    case_id: str,
    selected_services: List[str],
    saved_answers: Dict[str, Any],
    case_context: Dict[str, Any],
    policy_context: Optional[Dict[str, Any]] = None,
    company_id: Optional[str] = None,
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
    # Phase 0: the intake-captured office address is the single source of truth.
    office_address_case = (case_context.get("officeAddress") or "").strip()

    # Question key -> criteria_key mapping (from question_schema.ServiceQuestionDef)
    CRITERIA_MAP: Dict[str, str] = {
        "budget_min": "budget_min",
        "budget_max": "budget_max",
        "bedrooms": "bedrooms",
        "sqm_min": "sqm_min",
        "commute_mins": "commute_mins",
        "commute_mode": "commute_mode",
        "housing_lifestyle": "housing_lifestyle",
        "housing_subtype": "housing_subtype",
        "preferred_areas": "preferred_areas",
        "avoid_areas": "avoid_areas",
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
        "ins_type": "insurance_type",
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

        # Phase 0: prefer the intake office address over the (now-removed)
        # duplicate free-text question; keep any legacy answer as fallback.
        if svc_key == "housing" and office_address_case:
            criteria["office_address"] = office_address_case

        if svc_key == "spouse":
            fam = case_context.get("familyMembers") or {}
            spouse = fam.get("spouse") if isinstance(fam, dict) else None
            if isinstance(spouse, dict):
                criteria["_spouse"] = spouse

        criteria = _apply_service_shaping(svc_key, criteria)
        result[backend_key] = criteria
        # Fan out to any secondary backend categories (e.g. housing -> housing_agencies).
        # They read the same destination/budget shaping; category-specific fields they
        # don't declare are ignored by the plugin's criteria model.
        for extra_bk in EXTRA_BACKENDS_FOR_SERVICE.get(svc_key, []):
            result[extra_bk] = dict(criteria)

    # [AIQ-1530] The "+15 preferred" boost now reads HR's curation (company_vendor_selections
    # via service_catalog_items.supplier_id), not the retired company_preferred_suppliers table.
    # This marks curated suppliers as preferred (the boost + the company_preferred UI flag +
    # marketplace); HR's display_order ordering for the employee is applied downstream in
    # employee_recommendations_filter.apply_hr_curation, where only selected items remain.
    if company_id:
        try:
            from ...database import db
            for svc_key in selected_services:
                curated = db.list_company_curated_supplier_ids(company_id, svc_key)
                supplier_ids = [str(c.get("supplier_id", "")) for c in curated if c.get("supplier_id")]
                if not supplier_ids:
                    continue
                # Apply the preferred boost to every backend the service fans out to
                # (e.g. both living_areas and housing_agencies for "housing").
                for backend_key in backends_for_service(svc_key):
                    if backend_key in result:
                        result[backend_key]["_preferred_supplier_ids"] = supplier_ids
        except Exception:
            pass

    return result
