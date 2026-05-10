"""
Resolve applicable HR policy benefits for an employee based on band, assignment type, and jurisdiction.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


BENEFIT_LABELS: Dict[str, str] = {
    "preAssignmentVisit": "Pre-Assignment Visit",
    "travel": "Travel",
    "temporaryHousing": "Temporary Housing",
    "houseHunting": "House Hunting",
    "shipment": "Shipment",
    "storage": "Storage",
    "homeSalePurchase": "Home Sale/Purchase",
    "rentalAssistance": "Rental Assistance",
    "settlingInAllowance": "Settling-In Allowance",
    "visaImmigration": "Visa & Immigration",
    "taxAssistance": "Tax Assistance",
    "spousalSupport": "Spousal Support",
    "educationSupport": "Education Support",
    "languageTraining": "Language Training",
    "repatriation": "Repatriation",
}


def _get_benefit_from_policy(
    policy: Dict[str, Any],
    benefit_key: str,
    band: str,
    assignment_type: str,
    country_code: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Resolve benefit with override order: jurisdiction -> bandAssignment -> base."""
    base = policy.get("benefitCategories", {}).get(benefit_key)
    if not base:
        return None

    band_key = f"{band}_{assignment_type}"

    # 1. Jurisdiction override
    if country_code:
        jo = policy.get("jurisdictionOverrides", {}).get(country_code, {})
        overrides = jo.get("overrideBenefitCategories", {})
        if benefit_key in overrides:
            merged = dict(base)
            _merge_benefit(merged, overrides[benefit_key])
            return merged

    # 2. Band+assignment override
    bar = policy.get("bandAssignmentRules", {}).get(band_key, {})
    overrides = bar.get("benefitOverrides", {})
    if benefit_key in overrides:
        merged = dict(base)
        _merge_benefit(merged, overrides[benefit_key])
        return merged

    # 3. Fallback band
    fallback = bar.get("fallbackBand")
    if fallback:
        fkey = f"{fallback}_{assignment_type}"
        fbar = policy.get("bandAssignmentRules", {}).get(fkey, {})
        fover = fbar.get("benefitOverrides", {}).get(benefit_key)
        if fover:
            merged = dict(base)
            _merge_benefit(merged, fover)
            return merged

    return base


def _merge_benefit(target: Dict[str, Any], override: Dict[str, Any]) -> None:
    for k, v in override.items():
        if v is not None:
            if k == "maxAllowed" and isinstance(v, dict) and isinstance(target.get(k), dict):
                target[k] = {**target.get(k, {}), **v}
            else:
                target[k] = v


def resolve_applicable_benefits(
    policy: Dict[str, Any],
    employee_band: str,
    assignment_type: str,
    country_code: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Return list of allowed benefits with resolved max values for the employee context.
    """
    result = []
    categories = policy.get("benefitCategories", {})

    for benefit_key, benefit_def in categories.items():
        if not benefit_def.get("allowed"):
            continue

        resolved = _get_benefit_from_policy(
            policy, benefit_key, employee_band, assignment_type, country_code
        )
        if not resolved or not resolved.get("allowed"):
            continue

        max_allowed = resolved.get("maxAllowed", {})
        currency = resolved.get("currency", "USD")
        doc_req = resolved.get("documentationRequired", [])
        pre_approval = resolved.get("preApprovalRequired", False)
        notes = resolved.get("notes", "")

        premium = max_allowed.get("premium") or max_allowed.get("extensive") or max_allowed.get("medium") or max_allowed.get("min") or 0
        explanatory = f"Maximum allowance: {currency} {premium:,.0f} (Premium tier)"
        if pre_approval:
            explanatory += ". Pre-approval required."
        if notes:
            explanatory += f" {notes}"

        result.append({
            "key": benefit_key,
            "label": BENEFIT_LABELS.get(benefit_key, benefit_key),
            "allowed": True,
            "maxAllowed": max_allowed,
            "currency": currency,
            "preApprovalRequired": pre_approval,
            "documentationRequired": doc_req,
            "explanatoryText": explanatory,
            "notes": notes,
        })

    return result


def policy_to_wizard_criteria(
    policy: Dict[str, Any],
    employee_band: str,
    assignment_type: str,
    country_code: Optional[str] = None,
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Map policy benefits to wizard criteria for auto-fill.
    Maps: temporaryHousing -> budget, educationSupport -> school_budget, shipment -> movers hints.
    """
    criteria: Dict[str, Any] = {}

    def get_benefit(key: str) -> Optional[Dict[str, Any]]:
        return _get_benefit_from_policy(policy, key, employee_band, assignment_type, country_code)

    # Housing budget from temporaryHousing
    housing = get_benefit("temporaryHousing")
    if housing and housing.get("allowed"):
        ma = housing.get("maxAllowed", {})
        med = ma.get("medium") or ma.get("min") or 3000
        prem = ma.get("premium") or ma.get("extensive") or med
        criteria["budget_min"] = int(ma.get("min") or med * 0.5)
        criteria["budget_max"] = int(prem)
        criteria["dest_city"] = _extract_city(profile, "destination", "Singapore")

    # School budget from educationSupport
    edu = get_benefit("educationSupport")
    if edu and edu.get("allowed"):
        ma = edu.get("maxAllowed", {})
        med = ma.get("medium") or ma.get("min") or 20000
        school_budget_num = int(ma.get("premium") or ma.get("extensive") or med)
        criteria["school_budget"] = "high" if school_budget_num >= 35000 else "low" if school_budget_num <= 20000 else "medium"

    # Movers / shipment
    shipment = get_benefit("shipment")
    if shipment and shipment.get("allowed"):
        ma = shipment.get("maxAllowed", {})
        criteria["acc_type"] = "apartment"
        criteria["move_type"] = "international"
        criteria["origin_city"] = _extract_city(profile, "origin", "Oslo")
        criteria["move_dest"] = _extract_city(profile, "destination", "Singapore")

    return criteria


def _extract_city(profile: Optional[Dict[str, Any]], key: str, default: str) -> str:
    if not profile:
        return default
    mp = profile.get("movePlan") or {}
    val = mp.get(key, default)
    if isinstance(val, str) and "," in val:
        return val.split(",")[0].strip()
    return str(val or default)
