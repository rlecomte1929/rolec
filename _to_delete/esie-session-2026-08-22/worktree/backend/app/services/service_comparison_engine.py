"""
Effective-entitlement service comparison (ReloPass).

Uses per-rule ``rule_comparison_readiness`` (full / partial / not_ready) to decide whether
numeric envelope comparison is allowed. Never fabricates caps or deltas when currency/unit
or policy structure is insufficient.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .policy_entitlement_model import legacy_benefit_key_for_canonical_service
from .policy_rule_comparison_readiness import (
    RULE_COMPARISON_FULL,
    RULE_COMPARISON_NOT_READY,
    RULE_COMPARISON_PARTIAL,
)

# Initial product slice: canonical service_key -> Layer-2 benefit_key via entitlement model
COMPARISON_ENGINE_SERVICE_KEYS: Tuple[str, ...] = (
    "visa_support",
    "temporary_housing",
    "home_search",
    "school_search",
    "household_goods_shipment",
)


def _parse_rule_readiness(entitlement: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not entitlement:
        return {"level": RULE_COMPARISON_NOT_READY, "supports_budget_delta": False, "reasons": []}
    cr = entitlement.get("rule_comparison_readiness")
    if not isinstance(cr, dict):
        return {"level": RULE_COMPARISON_PARTIAL, "supports_budget_delta": False, "reasons": ["MISSING_RULE_READINESS"]}
    return {
        "level": cr.get("level") or RULE_COMPARISON_NOT_READY,
        "supports_budget_delta": bool(cr.get("supports_budget_delta")),
        "reasons": list(cr.get("reasons") or []),
    }


def _coverage_status_from_entitlement(ent: Dict[str, Any]) -> str:
    if not ent.get("included", True):
        return "excluded"
    if ent.get("max_value") is not None or ent.get("standard_value") is not None or ent.get("min_value") is not None:
        return "included"
    return "conditional"


def _policy_cap_for_comparison(ent: Dict[str, Any]) -> Optional[float]:
    """Comparable single cap: prefer max, then standard (resolved row fields)."""
    for k in ("max_value", "standard_value"):
        v = ent.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    return None


def _policy_limit_snapshot(ent: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not ent:
        return {}
    snap: Dict[str, Any] = {}
    for k in ("min_value", "standard_value", "max_value", "currency", "amount_unit", "frequency"):
        if ent.get(k) is not None:
            snap[k] = ent.get(k)
    return snap


def _selected_snapshot(sel: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in ("estimated_cost", "currency", "duration_months", "quantity", "unit"):
        if sel.get(k) is not None:
            out[k] = sel.get(k)
    return out


def _selected_amount(sel: Dict[str, Any]) -> Optional[float]:
    v = sel.get("estimated_cost")
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _currencies_compatible(policy_currency: Optional[str], selected_currency: Optional[str]) -> bool:
    pc = (policy_currency or "USD").strip().upper()
    sc = (selected_currency or "USD").strip().upper()
    return pc == sc


def _can_compute_numeric_delta(
    ent: Dict[str, Any],
    sel: Dict[str, Any],
    cr: Dict[str, Any],
    cap: Optional[float],
    selected_amount: Optional[float],
) -> Tuple[bool, str]:
    if selected_amount is None:
        return False, "no_selected_amount"
    if cap is None:
        return False, "no_policy_cap"
    if not _currencies_compatible(ent.get("currency"), sel.get("currency")):
        return False, "currency_mismatch"
    # Unit / frequency: without explicit conversion, only compare when policy amount is a flat total-like cap
    unit = (ent.get("amount_unit") or "").lower()
    freq = (ent.get("frequency") or "").lower()
    if unit in ("month", "monthly", "per_month") or "month" in freq:
        if sel.get("duration_months") is None:
            return False, "monthly_cap_without_duration"
    if cr["level"] == RULE_COMPARISON_NOT_READY:
        return False, "rule_not_ready"
    return True, "ok"


def compare_selected_services_effective_entitlements(
    *,
    selected_services: List[Dict[str, Any]],
    entitlements_by_benefit_key: Dict[str, Dict[str, Any]],
    version_comparison_ready: bool = True,
) -> List[Dict[str, Any]]:
    """
    For each selected service (canonical ``service_key``), compare against the effective
    entitlement for the mapped Layer-2 ``benefit_key``.

    ``entitlements_by_benefit_key``: resolved benefit rows, ideally enriched with
    ``rule_comparison_readiness`` (see ``enrich_resolved_benefits_with_rule_comparison``).

    Each ``selected_services`` item: ``service_key`` plus optional ``estimated_cost``, ``currency``,
    ``duration_months``, ``quantity``, ``unit``.
    """
    out: List[Dict[str, Any]] = []
    for sel in selected_services:
        sk = (sel.get("service_key") or "").strip()
        if not sk:
            continue
        if sk not in COMPARISON_ENGINE_SERVICE_KEYS:
            continue
        legacy = legacy_benefit_key_for_canonical_service(sk)
        ent = entitlements_by_benefit_key.get(legacy) if legacy else None
        cr = _parse_rule_readiness(ent)
        approval = bool(ent.get("approval_required")) if ent else False

        policy_snap = _policy_limit_snapshot(ent)
        selected_snap = _selected_snapshot(sel)
        cap = _policy_cap_for_comparison(ent) if ent else None
        selected_amount = _selected_amount(sel)

        if not legacy or ent is None:
            out.append(
                {
                    "service_key": sk,
                    "coverage_status": "unknown",
                    "comparison_status": "not_enough_policy_data",
                    "policy_limit_snapshot": {},
                    "selected_value_snapshot": selected_snap,
                    "delta": None,
                    "explanation": "No effective entitlement row for this service in the policy matrix.",
                    "approval_required": False,
                }
            )
            continue

        cov = _coverage_status_from_entitlement(ent)

        if not ent.get("included", True):
            out.append(
                {
                    "service_key": sk,
                    "coverage_status": "excluded",
                    "comparison_status": "excluded",
                    "policy_limit_snapshot": policy_snap,
                    "selected_value_snapshot": selected_snap,
                    "delta": None,
                    "explanation": ent.get("condition_summary") or "This service is excluded under your employer policy.",
                    "approval_required": False,
                }
            )
            continue

        if cr["level"] == RULE_COMPARISON_NOT_READY:
            out.append(
                {
                    "service_key": sk,
                    "coverage_status": cov,
                    "comparison_status": "not_enough_policy_data",
                    "policy_limit_snapshot": policy_snap,
                    "selected_value_snapshot": selected_snap,
                    "delta": None,
                    "explanation": "Policy wording or structure is too weak for automated cost comparison; confirm with HR.",
                    "approval_required": approval,
                }
            )
            continue

        # Partial rule without budget-delta support: never compute numeric variance (even if Layer-2 has numbers).
        if cr["level"] == RULE_COMPARISON_PARTIAL and not cr["supports_budget_delta"]:
            expl = (
                "Coverage is informational under this rule; automated envelope comparison is not enabled."
                if cap is None
                else "A limit appears on file, but this rule is not comparison-ready for automated within/exceed checks."
            )
            out.append(
                {
                    "service_key": sk,
                    "coverage_status": cov,
                    "comparison_status": "information_only",
                    "policy_limit_snapshot": policy_snap,
                    "selected_value_snapshot": selected_snap,
                    "delta": None,
                    "explanation": expl,
                    "approval_required": approval,
                }
            )
            continue

        can_delta, why = _can_compute_numeric_delta(ent, sel, cr, cap, selected_amount)
        if not can_delta:
            if cap is None and cov == "conditional":
                expl = "Included under policy, but there is no numeric cap to compare against your estimate."
            elif selected_amount is None:
                expl = "Add an estimated cost to compare against your policy limit."
            elif why == "currency_mismatch":
                expl = "Selected currency does not match the policy currency; numeric delta is not computed."
            elif why == "monthly_cap_without_duration":
                expl = "Policy limit is monthly; provide assignment duration to compare meaningfully."
            elif why == "partial_no_budget_delta":
                expl = "Policy allows informational coverage only; envelope comparison is not enabled for this rule."
            else:
                expl = "Not enough structured policy data to compute a numeric comparison."
            out.append(
                {
                    "service_key": sk,
                    "coverage_status": cov,
                    "comparison_status": "conditional",
                    "policy_limit_snapshot": policy_snap,
                    "selected_value_snapshot": selected_snap,
                    "delta": None,
                    "explanation": expl,
                    "approval_required": approval,
                }
            )
            continue

        assert cap is not None and selected_amount is not None
        delta = selected_amount - cap
        if delta > 0:
            cmp_status = "exceeds_envelope"
            expl = (
                f"Estimate exceeds policy cap by {delta:,.2f} {ent.get('currency') or 'USD'}."
                + (" Pre-approval may be required." if approval else "")
            )
        else:
            cmp_status = "within_envelope"
            expl = f"Estimate is within the policy cap ({ent.get('currency') or 'USD'} {cap:,.2f})."

        if not version_comparison_ready and cmp_status in ("within_envelope", "exceeds_envelope"):
            cmp_status = "not_enough_policy_data"
            delta = None
            expl = (
                "This policy version is not fully comparison-ready; automated within/exceed envelope results are not shown."
            )

        out.append(
            {
                "service_key": sk,
                "coverage_status": cov,
                "comparison_status": cmp_status,
                "policy_limit_snapshot": policy_snap,
                "selected_value_snapshot": selected_snap,
                "delta": None if delta is None else round(delta, 4),
                "explanation": expl,
                "approval_required": approval,
            }
        )
    return out


def build_entitlements_by_benefit_key(benefits: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Index resolved benefits by benefit_key (last wins if duplicates)."""
    out: Dict[str, Dict[str, Any]] = {}
    for b in benefits:
        bk = (b.get("benefit_key") or "").strip()
        if bk:
            out[bk] = b
    return out


def map_case_service_to_canonical_selection(case_service: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Map a case_services row (category/service_key) to canonical service_key + cost fields.
    """
    raw = (case_service.get("service_key") or case_service.get("category") or "").lower().strip()
    if not raw:
        return None
    alias = {
        "housing": "temporary_housing",
        "living_areas": "temporary_housing",
        "schools": "school_search",
        "movers": "household_goods_shipment",
        "immigration": "visa_support",
        "visa": "visa_support",
        "home_search": "home_search",
        "relocation_services": "home_search",
    }
    sk = alias.get(raw, raw)
    if sk not in COMPARISON_ENGINE_SERVICE_KEYS:
        return None
    sel: Dict[str, Any] = {"service_key": sk}
    est = case_service.get("estimated_cost")
    if est is not None:
        try:
            sel["estimated_cost"] = float(est)
        except (TypeError, ValueError):
            pass
    if case_service.get("currency"):
        sel["currency"] = case_service.get("currency")
    return sel
