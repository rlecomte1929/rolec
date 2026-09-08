"""
Normalized policy caps for cross-module comparison with provider estimates.

Not tied to a single vendor: any module can pass monetary estimates + benefit_key + context.
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Tuple

from .policy_config_matrix_service import _normalize_cap_rule

# --- Normalized cap types (stable contract for downstream modules) ---
NORMALIZED_CURRENCY_AMOUNT = "currency_amount"
NORMALIZED_PERCENTAGE = "percentage"
NORMALIZED_NO_MONETARY_CAP = "no_monetary_cap"
NORMALIZED_UNSUPPORTED = "unsupported"


def _parse_conditions_json(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            o = json.loads(raw)
            return o if isinstance(o, dict) else {}
        except Exception:
            return {}
    return {}


def _effective_currency_amount_cap(
    b: Dict[str, Any],
) -> Tuple[Optional[str], Optional[float], Optional[str]]:
    """
    Returns (currency, comparable_max_amount, reason_if_unsupported).
    Uses min(amount_value, cap_rule.cap_amount) when both exist and currencies align.
    """
    vt = str(b.get("value_type") or "none").lower()
    cr = _normalize_cap_rule(b.get("cap_rule_json"))
    row_currency = str(b.get("currency_code") or "EUR").strip().upper() or "EUR"
    amt = b.get("amount_value")
    cap_amt = cr.get("cap_amount")
    cap_currency = str(cr.get("currency") or row_currency).strip().upper() or row_currency

    if vt != "currency":
        return row_currency, None, None

    if amt is None:
        if cap_amt is None:
            return row_currency, None, None
        try:
            return cap_currency, float(cap_amt), None
        except (TypeError, ValueError):
            return row_currency, None, "invalid_cap_amount"

    try:
        base = float(amt)
    except (TypeError, ValueError):
        return row_currency, None, "invalid_amount_value"

    if cap_amt is None:
        return row_currency, base, None

    try:
        cfloat = float(cap_amt)
    except (TypeError, ValueError):
        return row_currency, base, None

    if cap_currency != row_currency:
        return row_currency, None, "mixed_currency_amount_and_cap_rule"

    return row_currency, min(base, cfloat), None


def normalized_cap_record_from_benefit_row(b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a published policy_config_benefits row to the public caps API shape.
    """
    vt = str(b.get("value_type") or "none").lower()
    bk = str(b.get("benefit_key") or "")
    label = b.get("benefit_label")
    category = b.get("category")
    covered = bool(b.get("covered"))
    unit_frequency = b.get("unit_frequency") or "one_time"
    notes = b.get("notes")
    conditions_json = _parse_conditions_json(b.get("conditions_json"))

    normalized_cap_type: str
    normalized_amount: Optional[float] = None
    currency_code: Optional[str] = None
    comparison_note: Optional[str] = None

    if vt == "percentage" and b.get("percentage_value") is not None:
        try:
            normalized_amount = float(b["percentage_value"])
        except (TypeError, ValueError):
            normalized_amount = None
        normalized_cap_type = NORMALIZED_PERCENTAGE
    elif vt == "currency":
        cur, eff, reason = _effective_currency_amount_cap(b)
        currency_code = cur
        if reason == "mixed_currency_amount_and_cap_rule":
            normalized_cap_type = NORMALIZED_UNSUPPORTED
            comparison_note = "amount and cap_rule use different currencies; normalize externally"
        elif eff is not None:
            normalized_cap_type = NORMALIZED_CURRENCY_AMOUNT
            normalized_amount = eff
        else:
            normalized_cap_type = NORMALIZED_NO_MONETARY_CAP
            comparison_note = reason or "no_numeric_allowance_on_row"
    elif vt == "text":
        normalized_cap_type = NORMALIZED_NO_MONETARY_CAP
        comparison_note = "text_value_type"
    else:
        # none / qualitative covered
        if covered and vt == "none":
            normalized_cap_type = NORMALIZED_NO_MONETARY_CAP
            comparison_note = "covered_without_structured_amount"
        else:
            normalized_cap_type = NORMALIZED_NO_MONETARY_CAP
            comparison_note = "not_quantified"

    out: Dict[str, Any] = {
        "benefit_key": bk,
        "benefit_label": label,
        "category": category,
        "covered": covered,
        "normalized_cap_type": normalized_cap_type,
        "normalized_amount": normalized_amount,
        "currency_code": currency_code,
        "unit_frequency": unit_frequency,
        "notes": notes,
        "conditions_json": conditions_json,
    }
    if comparison_note:
        out["comparison_note"] = comparison_note
    return out


def compare_provider_estimate_to_normalized_cap(
    *,
    estimate_amount: float,
    estimate_currency: str,
    normalized_cap: Dict[str, Any],
    epsilon: float = 1e-6,
) -> Dict[str, Any]:
    """
    Compare a single monetary provider estimate to one normalized cap row.

    Returns keys: supported_comparison, within_cap, cap_amount, estimate_amount,
    difference_amount, difference_direction, currency_code, reason_unsupported
    """
    est_cur = str(estimate_currency or "").strip().upper()
    try:
        est_amt = float(estimate_amount)
    except (TypeError, ValueError):
        return {
            "supported_comparison": False,
            "within_cap": None,
            "cap_amount": None,
            "estimate_amount": None,
            "difference_amount": None,
            "difference_direction": None,
            "currency_code": est_cur or None,
            "reason_unsupported": "invalid_estimate_amount",
        }
    if not math.isfinite(est_amt):
        return {
            "supported_comparison": False,
            "within_cap": None,
            "cap_amount": None,
            "estimate_amount": None,
            "difference_amount": None,
            "difference_direction": None,
            "currency_code": est_cur or None,
            "reason_unsupported": "invalid_estimate_amount",
        }

    ntype = str(normalized_cap.get("normalized_cap_type") or "")
    if ntype == NORMALIZED_UNSUPPORTED:
        return {
            "supported_comparison": False,
            "within_cap": None,
            "cap_amount": None,
            "estimate_amount": est_amt,
            "difference_amount": None,
            "difference_direction": None,
            "currency_code": est_cur or None,
            "reason_unsupported": normalized_cap.get("comparison_note") or "cap_unsupported",
        }

    if ntype == NORMALIZED_PERCENTAGE:
        return {
            "supported_comparison": False,
            "within_cap": None,
            "cap_amount": normalized_cap.get("normalized_amount"),
            "estimate_amount": est_amt,
            "difference_amount": None,
            "difference_direction": None,
            "currency_code": est_cur or None,
            "reason_unsupported": "percentage_cap_requires_separate_logic_or_base_amount",
        }

    if ntype == NORMALIZED_NO_MONETARY_CAP:
        return {
            "supported_comparison": False,
            "within_cap": None,
            "cap_amount": None,
            "estimate_amount": est_amt,
            "difference_amount": None,
            "difference_direction": None,
            "currency_code": est_cur or None,
            "reason_unsupported": normalized_cap.get("comparison_note") or "no_monetary_cap",
        }

    if ntype != NORMALIZED_CURRENCY_AMOUNT:
        return {
            "supported_comparison": False,
            "within_cap": None,
            "cap_amount": None,
            "estimate_amount": est_amt,
            "difference_amount": None,
            "difference_direction": None,
            "currency_code": est_cur or None,
            "reason_unsupported": f"unknown_cap_type:{ntype}",
        }

    cap_amt = normalized_cap.get("normalized_amount")
    cap_cur = str(normalized_cap.get("currency_code") or "").strip().upper()
    if cap_amt is None:
        return {
            "supported_comparison": False,
            "within_cap": None,
            "cap_amount": None,
            "estimate_amount": est_amt,
            "difference_amount": None,
            "difference_direction": None,
            "currency_code": est_cur or None,
            "reason_unsupported": "missing_normalized_amount",
        }
    try:
        cap_f = float(cap_amt)
    except (TypeError, ValueError):
        return {
            "supported_comparison": False,
            "within_cap": None,
            "cap_amount": None,
            "estimate_amount": est_amt,
            "difference_amount": None,
            "difference_direction": None,
            "currency_code": est_cur or None,
            "reason_unsupported": "invalid_cap_amount",
        }

    if not est_cur or not cap_cur or est_cur != cap_cur:
        return {
            "supported_comparison": False,
            "within_cap": None,
            "cap_amount": cap_f,
            "estimate_amount": est_amt,
            "difference_amount": None,
            "difference_direction": None,
            "currency_code": est_cur or cap_cur or None,
            "reason_unsupported": "currency_mismatch",
        }

    diff = est_amt - cap_f
    if abs(diff) <= epsilon:
        direction = "equal"
        abs_diff = 0.0
    elif diff > 0:
        direction = "over"
        abs_diff = diff
    else:
        direction = "under"
        abs_diff = -diff

    return {
        "supported_comparison": True,
        "within_cap": est_amt <= cap_f + epsilon,
        "cap_amount": cap_f,
        "estimate_amount": est_amt,
        "difference_amount": abs_diff,
        "difference_direction": direction,
        "currency_code": cap_cur,
        "reason_unsupported": None,
    }


def evaluate_estimates_against_caps(
    estimates: List[Dict[str, Any]],
    caps: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Batch compare provider lines to a pre-built normalized caps list.
    Each estimate dict: benefit_key, amount, currency (any extra keys preserved in output under _extra).
    """
    by_key: Dict[str, Dict[str, Any]] = {}
    for c in caps:
        k = str(c.get("benefit_key") or "").strip()
        if k:
            by_key[k] = c

    results: List[Dict[str, Any]] = []
    for raw in estimates:
        bk = str(raw.get("benefit_key") or "").strip()
        if not bk:
            results.append(
                {
                    "benefit_key": "",
                    "matched_cap": False,
                    "supported_comparison": False,
                    "reason_unsupported": "missing_benefit_key",
                }
            )
            continue
        cap = by_key.get(bk)
        if not cap:
            results.append(
                {
                    "benefit_key": bk,
                    "matched_cap": False,
                    "supported_comparison": False,
                    "reason_unsupported": "no_cap_for_benefit_in_context",
                }
            )
            continue
        comp = compare_provider_estimate_to_normalized_cap(
            estimate_amount=float(raw.get("amount", 0)),
            estimate_currency=str(raw.get("currency") or ""),
            normalized_cap=cap,
        )
        row: Dict[str, Any] = {
            "benefit_key": bk,
            "matched_cap": True,
            "normalized_cap_type": cap.get("normalized_cap_type"),
            **comp,
        }
        results.append(row)
    return results
