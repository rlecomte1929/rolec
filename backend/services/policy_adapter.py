from typing import Any, Dict


DEFAULT_CURRENCY = "USD"


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
