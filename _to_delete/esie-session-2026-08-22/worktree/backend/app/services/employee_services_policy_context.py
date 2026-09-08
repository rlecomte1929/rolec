"""
Employee Services page: per-category view model from **Layer 2 only** (resolved published policy).

Uses `resolved_assignment_policy` benefits — the same snapshot as policy resolution / comparison.
Never reads policy_documents.extracted_metadata or clause hints.

See docs/policy/services-page-policy-consumption.md.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .policy_adapter import DEFAULT_CURRENCY
from .policy_service_comparison import SERVICE_TO_BENEFIT
from .policy_taxonomy import get_benefit_meta

# Wizard / case `category` keys used by enabled Services (matches serviceConfig.backendKey).
SERVICES_WIZARD_KEYS: Tuple[str, ...] = (
    "living_areas",
    "movers",
    "schools",
    "banks",
    "insurance",
    "electricity",
)


def _best_benefit_for_key(benefits: List[Dict[str, Any]], benefit_key: str) -> Optional[Dict[str, Any]]:
    rows = [b for b in benefits if (b.get("benefit_key") or "") == benefit_key]
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]

    def score(b: Dict[str, Any]) -> Tuple[int, float]:
        inc = 1 if b.get("included") else 0
        cap = b.get("max_value")
        std = b.get("standard_value")
        m = 0.0
        for v in (cap, std, b.get("min_value")):
            if v is not None:
                try:
                    m = max(m, float(v))
                except (TypeError, ValueError):
                    pass
        return (inc, m)

    return max(rows, key=score)


def _format_cap_line(b: Dict[str, Any]) -> Optional[str]:
    cur = b.get("currency") or DEFAULT_CURRENCY
    for k in ("max_value", "standard_value", "min_value"):
        v = b.get(k)
        if v is None:
            continue
        try:
            n = float(v)
            if n > 0:
                return f"Policy limit: {cur} {n:,.0f}"
        except (TypeError, ValueError):
            continue
    return None


def build_employee_services_policy_context(resolution: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build JSON for GET .../services-policy-context.

    `resolution` must be the dict from `_resolve_published_policy_for_employee`
    (has_policy, comparison_available, comparison_readiness, benefits, ...).
    """
    has_policy = bool(resolution.get("has_policy"))
    comparison_available = bool(resolution.get("comparison_available"))
    benefits = resolution.get("benefits") or []
    if not isinstance(benefits, list):
        benefits = []

    currency = DEFAULT_CURRENCY
    for b in benefits:
        if b.get("currency"):
            currency = b.get("currency") or currency
            break

    categories: Dict[str, Any] = {}

    # Resolution often omits benefit rows when comparison is off; avoid "no rule" false negatives.
    if has_policy and not comparison_available:
        for wkey in SERVICES_WIZARD_KEYS:
            mapped = SERVICE_TO_BENEFIT.get(wkey)
            if mapped == "out_of_scope" or mapped is None:
                categories[wkey] = {
                    "wizard_key": wkey,
                    "benefit_key": None,
                    "determination": "out_of_scope",
                    "show_policy_comparison": False,
                    "primary_label": "Outside standard policy comparison",
                    "detail": "This category is not compared against relocation policy limits in ReloPass.",
                }
                continue
            categories[wkey] = {
                "wizard_key": wkey,
                "benefit_key": mapped,
                "determination": "comparison_not_ready",
                "show_policy_comparison": False,
                "primary_label": "Policy limits not shown yet",
                "detail": (
                    "Your company has a published policy, but per-category limits are hidden until the policy "
                    "meets comparison requirements. You can still review service costs."
                ),
            }
        return {
            "ok": True,
            "has_policy": has_policy,
            "comparison_available": comparison_available,
            "comparison_readiness": resolution.get("comparison_readiness"),
            "currency": currency,
            "categories": categories,
            "source": "resolved_assignment_policy",
        }

    for wkey in SERVICES_WIZARD_KEYS:
        mapped = SERVICE_TO_BENEFIT.get(wkey)
        if mapped == "out_of_scope" or mapped is None:
            categories[wkey] = {
                "wizard_key": wkey,
                "benefit_key": None,
                "determination": "out_of_scope",
                "show_policy_comparison": False,
                "primary_label": "Outside standard policy comparison",
                "detail": "This category is not compared against relocation policy limits in ReloPass.",
            }
            continue

        benefit_key = mapped
        if not has_policy:
            categories[wkey] = {
                "wizard_key": wkey,
                "benefit_key": benefit_key,
                "determination": "no_published_policy",
                "show_policy_comparison": False,
                "primary_label": "No published policy yet",
                "detail": None,
            }
            continue

        b = _best_benefit_for_key(benefits, benefit_key)
        if b is None:
            categories[wkey] = {
                "wizard_key": wkey,
                "benefit_key": benefit_key,
                "determination": "no_benefit_rule",
                "show_policy_comparison": False,
                "primary_label": "No policy rule for this category",
                "detail": "Your published policy does not define this benefit yet.",
            }
            continue

        included = bool(b.get("included"))
        approval = bool(b.get("approval_required"))
        cap_line = _format_cap_line(b)
        cond = (b.get("condition_summary") or "").strip() or None
        meta = get_benefit_meta(benefit_key)
        friendly = (meta.get("keywords") or [benefit_key.replace("_", " ")])[0]

        if not included:
            categories[wkey] = {
                "wizard_key": wkey,
                "benefit_key": benefit_key,
                "determination": "excluded",
                "show_policy_comparison": False,
                "primary_label": "Not covered by policy",
                "detail": cond or f"{friendly} is not included under your assignment policy.",
            }
            continue

        show_compare = bool(comparison_available and (cap_line is not None or approval))

        if approval and cap_line:
            determination = "capped_with_approval"
        elif approval:
            determination = "approval_required"
        elif cap_line:
            determination = "capped"
        else:
            determination = "included_partial"

        if determination == "included_partial":
            primary = "Covered — details on HR Policy page"
            detail = (
                "Your policy includes this benefit, but a machine-readable limit is not set yet. "
                "See Assignment Package & Limits for wording from HR."
            )
        elif determination == "approval_required":
            primary = "Pre-approval required"
            detail = cond or "HR or manager approval is required before using this benefit."
        elif determination == "capped":
            primary = cap_line or "Policy limit applies"
            detail = cond
        else:
            primary = cap_line or "Policy limit applies"
            detail = cond

        categories[wkey] = {
            "wizard_key": wkey,
            "benefit_key": benefit_key,
            "determination": determination,
            "show_policy_comparison": show_compare,
            "primary_label": primary,
            "detail": detail,
            "approval_required": approval,
            "cap_summary": cap_line,
        }

    return {
        "ok": True,
        "has_policy": has_policy,
        "comparison_available": comparison_available,
        "comparison_readiness": resolution.get("comparison_readiness"),
        "currency": currency,
        "categories": categories,
        "source": "resolved_assignment_policy",
    }
