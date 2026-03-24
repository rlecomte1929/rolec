from typing import Any, Dict, List, Optional

DEFAULT_CURRENCY = "USD"

# Map resolved benefit_key to cap key used by frontend (Services page, policy-budget).
# Align with policy_service_comparison.SERVICE_TO_BENEFIT and frontend service keys.
# Cap keys match frontend service categories (case_services.category, EmployeeJourney caps[category]).
BENEFIT_KEY_TO_CAP_KEY: Dict[str, str] = {
    "temporary_housing": "housing",
    "temporary_living": "housing",
    "host_housing_cap": "housing",
    "housing": "housing",
    "shipment": "movers",
    "shipment_of_goods": "movers",
    "removal_expenses": "movers",
    "storage": "movers",
    "movers": "movers",
    "relocation": "movers",
    "household_goods": "movers",
    "relocation_services": "movers",
    "settling_in_allowance": "movers",
    "schooling": "schools",
    "child_education_support": "schools",
    "tuition": "schools",
    "education": "schools",
    "banking_setup": "banking",
    "insurance": "insurance",
    "medical": "insurance",
    "transport": "travel",
    "home_leave": "travel",
    "scouting_trip": "travel",
}


def caps_from_resolved_benefits(benefits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build policy-budget shape { currency, caps, total_cap } from resolved policy benefits.
    Used so employee Services page shows the same caps as Assignment Package & Limits.
    """
    caps: Dict[str, float] = {}
    currency = DEFAULT_CURRENCY
    total_cap: Optional[float] = None

    for b in benefits:
        if not b.get("included"):
            continue
        benefit_key = (b.get("benefit_key") or "").strip()
        if not benefit_key:
            continue
        cap_key = BENEFIT_KEY_TO_CAP_KEY.get(benefit_key) or benefit_key
        amount = None
        if b.get("max_value") is not None:
            try:
                amount = float(b["max_value"])
            except (TypeError, ValueError):
                pass
        if amount is None and b.get("standard_value") is not None:
            try:
                amount = float(b["standard_value"])
            except (TypeError, ValueError):
                pass
        if amount is not None and amount > 0:
            existing = caps.get(cap_key)
            if existing is None or amount > existing:
                caps[cap_key] = amount
        if b.get("currency"):
            currency = b["currency"]

    return {
        "currency": currency or DEFAULT_CURRENCY,
        "caps": caps,
        "total_cap": total_cap,
    }


def normalize_policy_caps(policy: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert policy caps to a normalized structure for services comparison.
    """
    caps = policy.get("caps", {}) if isinstance(policy, dict) else {}
    currency = DEFAULT_CURRENCY
    normalized_caps: Dict[str, float] = {}
    total_cap = None

    key_map = {
        "movers": "moving",
    }

    for key, value in caps.items():
        if not isinstance(value, dict):
            continue
        amount = value.get("amount")
        if amount is None:
            continue
        mapped_key = key_map.get(key, key)
        normalized_caps[mapped_key] = float(amount)
        if not currency:
            currency = value.get("currency") or DEFAULT_CURRENCY
        else:
            currency = value.get("currency") or currency

    if isinstance(policy, dict):
        total_cap = policy.get("total_cap") or policy.get("totalCap")

    return {
        "currency": currency or DEFAULT_CURRENCY,
        "caps": normalized_caps,
        "total_cap": total_cap,
    }
