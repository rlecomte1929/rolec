"""
Recommendation Explanation Layer — builds structured explainability metadata.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_explanation(
    item: Dict[str, Any],
    scored_result: Dict[str, Any],
    criteria: Dict[str, Any],
    category: str,
) -> Dict[str, Any]:
    """
    Build explanation metadata from plugin score result and criteria.

    Returns: match_reasons, destination_fit, service_fit, budget_fit, family_fit,
             policy_fit, coverage_fit, warning_flags, explanation_summary
    """
    breakdown = scored_result.get("breakdown") or {}
    pros = scored_result.get("pros") or []
    cons = scored_result.get("cons") or []
    metadata = scored_result.get("metadata") or {}
    score_raw = scored_result.get("score_raw", 0)

    match_reasons: List[str] = list(pros)[:5]

    destination_fit = "match" if score_raw > 0 else "mismatch"

    service_fit = _derive_service_fit(breakdown, category)

    budget_fit, budget_reason = _derive_budget_fit(breakdown, pros, cons, metadata, criteria, category)
    if budget_reason and budget_reason not in match_reasons:
        if "within" in budget_reason.lower() or "budget" in budget_reason.lower():
            match_reasons.insert(0, budget_reason)
        else:
            match_reasons.append(budget_reason)

    family_fit = _derive_family_fit(breakdown, metadata, category)

    policy_fit, policy_flags = _derive_policy_fit(metadata, criteria, category)

    coverage_fit = _derive_coverage_fit(breakdown, metadata, category)

    warning_flags: List[str] = []
    for c in cons:
        flag = _cons_to_warning_flag(c)
        if flag and flag not in warning_flags:
            warning_flags.append(flag)
    for pf in policy_flags:
        if pf not in warning_flags:
            warning_flags.append(pf)
    if budget_fit == "above_budget" and "above_budget" not in warning_flags:
        warning_flags.append("above_budget")
    if metadata.get("availability_level") in ("low", "scarce"):
        if "low_availability" not in warning_flags:
            warning_flags.append("low_availability")

    explanation_summary = _build_summary(
        match_reasons=match_reasons,
        warning_flags=warning_flags,
        rationale=scored_result.get("rationale", ""),
    )

    return {
        "match_reasons": match_reasons,
        "destination_fit": destination_fit,
        "service_fit": service_fit,
        "budget_fit": budget_fit,
        "family_fit": family_fit,
        "policy_fit": policy_fit,
        "coverage_fit": coverage_fit,
        "warning_flags": warning_flags,
        "explanation_summary": explanation_summary,
        "score_dimensions": _normalize_breakdown(breakdown),
    }


def _derive_service_fit(breakdown: Dict[str, float], category: str) -> str:
    keys = list(breakdown.keys())
    service_keys = [k for k in keys if "service" in k.lower() or "fit" in k.lower() or "capacity" in k.lower()]
    if not service_keys:
        return "unknown"
    vals = [breakdown[k] for k in service_keys if isinstance(breakdown[k], (int, float))]
    if not vals:
        return "unknown"
    avg = sum(vals) / len(vals)
    if avg >= 80:
        return "strong"
    if avg >= 50:
        return "adequate"
    return "weak"


def _derive_budget_fit(
    breakdown: Dict[str, float],
    pros: List[str],
    cons: List[str],
    metadata: Dict[str, Any],
    criteria: Dict[str, Any],
    category: str,
) -> tuple:
    if "budget" in breakdown:
        b = breakdown["budget"]
        if b >= 90:
            return "within", next((p for p in pros if "budget" in p.lower() or "within" in p.lower()), None)
        if b < 50:
            return "above_budget", next((c for c in cons if "budget" in c.lower() or "above" in c.lower()), None)
        return "partial", None
    if "cost" in breakdown:
        c = breakdown["cost"]
        if c >= 70:
            return "within", None
        if c < 40:
            return "above_budget", None
        return "partial", None
    above = any("above budget" in (c or "").lower() for c in cons)
    within = any("within budget" in (p or "").lower() for p in pros)
    if above:
        return "above_budget", "Above your budget range"
    if within:
        return "within", "Within your budget"
    return "unknown", None


def _derive_family_fit(breakdown: Dict[str, float], metadata: Dict[str, Any], category: str) -> str:
    family_keys = [k for k in breakdown if "family" in k.lower() or "space" in k.lower()]
    if family_keys:
        vals = [breakdown[k] for k in family_keys if isinstance(breakdown[k], (int, float))]
        if vals:
            avg = sum(vals) / len(vals)
            return "strong" if avg >= 80 else "adequate" if avg >= 50 else "weak"
    return "unknown"


def _derive_policy_fit(
    metadata: Dict[str, Any],
    criteria: Dict[str, Any],
    category: str,
) -> tuple:
    flags: List[str] = []
    policy_cap = None
    cost = metadata.get("estimated_cost_usd") or metadata.get("estimated_cost_local")
    cost_type = metadata.get("cost_type", "one_time")

    if category in ("living_areas", "housing"):
        policy_cap = criteria.get("_policy_cap_monthly")
    elif category == "schools":
        policy_cap = criteria.get("_policy_cap_annual")
    elif category == "movers":
        policy_cap = criteria.get("_policy_cap_one_time")

    if policy_cap is not None and cost is not None:
        try:
            cost_f = float(cost)
            cap_f = float(policy_cap)
            if cost_f > cap_f:
                flags.append("above_policy")
                return "above_policy", flags
            if cost_f <= cap_f * 0.95:
                return "within", flags
            return "near_limit", flags
        except (TypeError, ValueError):
            pass
    return "unknown", flags


def _derive_coverage_fit(breakdown: Dict[str, float], metadata: Dict[str, Any], category: str) -> str:
    cov_keys = [k for k in breakdown if "coverage" in k.lower() or "availability" in k.lower() or "language" in k.lower()]
    if cov_keys:
        vals = [breakdown[k] for k in cov_keys if isinstance(breakdown[k], (int, float))]
        if vals:
            avg = sum(vals) / len(vals)
            return "strong" if avg >= 80 else "adequate" if avg >= 50 else "weak"
    return "unknown"


def _cons_to_warning_flag(con: str) -> Optional[str]:
    c = (con or "").lower()
    if "wrong city" in c or "wrong destination" in c:
        return "wrong_destination"
    if "above budget" in c or "over budget" in c:
        return "above_budget"
    if "limited availability" in c or "low availability" in c or "scarce" in c:
        return "low_availability"
    if "above policy" in c or "policy" in c:
        return "above_policy"
    if "waitlist" in c:
        return "waitlist"
    return None


def _normalize_breakdown(breakdown: Dict[str, float]) -> Dict[str, float]:
    out = {}
    for k, v in (breakdown or {}).items():
        if isinstance(v, (int, float)):
            out[k] = round(float(v), 1)
    return out


def _build_summary(
    match_reasons: List[str],
    warning_flags: List[str],
    rationale: str,
) -> str:
    if not match_reasons and not warning_flags:
        return rationale[:200] if rationale else "Recommended based on your preferences."
    parts = []
    if match_reasons:
        top = match_reasons[:3]
        parts.append("Matches: " + "; ".join(top))
    if warning_flags:
        flags_readable = {
            "above_budget": "Above budget",
            "above_policy": "Above policy limit",
            "low_availability": "Limited availability",
            "wrong_destination": "Wrong destination",
            "waitlist": "Waitlist may apply",
        }
        warn_strs = [flags_readable.get(f, f) for f in warning_flags[:3]]
        parts.append("Note: " + ", ".join(warn_strs))
    return " ".join(parts)
