"""
HR override layer: adjusts effective Layer-2 entitlements without changing extraction or normalization draft.

Effective values feed employee resolution and comparison; baseline rows stay the normalized/publishable source.
"""
from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Optional, Tuple

# Stable API keys for clients (HR review + employee traces)
TRACE_BASELINE = "baseline"
TRACE_HR_OVERRIDE = "hr_override"
TRACE_EFFECTIVE = "effective"


def _parse_meta(rule: Dict[str, Any]) -> Dict[str, Any]:
    raw = rule.get("metadata_json") or rule.get("metadata") or {}
    if isinstance(raw, str):
        try:
            return json.loads(raw) if raw.strip() else {}
        except Exception:
            return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _baseline_financial(rule: Dict[str, Any]) -> Dict[str, Any]:
    meta = _parse_meta(rule)
    return {
        "amount_value": rule.get("amount_value"),
        "amount_unit": rule.get("amount_unit"),
        "currency": rule.get("currency"),
        "frequency": rule.get("frequency"),
        "calc_type": rule.get("calc_type"),
        "approval_required": bool(meta.get("approval_required")),
        "allowed": meta.get("allowed", True),
    }


def _normalize_override_row(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    out = dict(row)
    dq = out.get("duration_quantity_json")
    if isinstance(dq, str) and dq.strip():
        try:
            out["duration_quantity_json"] = json.loads(dq)
        except Exception:
            out["duration_quantity_json"] = None
    return out


def index_hr_overrides_by_benefit_rule_id(overrides: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for o in overrides:
        brid = o.get("benefit_rule_id")
        if brid is not None:
            out[str(brid)] = _normalize_override_row(o) or {}
    return out


def compute_entitlement_value_trace(
    rule: Dict[str, Any],
    override_row: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Human-readable breakdown: baseline (Layer-2 normalized), HR override row, effective merge.
    """
    rid = rule.get("id")
    bk = rule.get("benefit_key")
    baseline = {
        "benefit_rule_id": rid,
        "benefit_key": bk,
        **_baseline_financial(rule),
        "service_visibility": "included",
    }
    hr_layer: Optional[Dict[str, Any]] = None
    if override_row:
        hr_layer = {
            "override_id": override_row.get("id"),
            "service_visibility": override_row.get("service_visibility"),
            "amount_value_override": override_row.get("amount_value_override"),
            "amount_unit_override": override_row.get("amount_unit_override"),
            "currency_override": override_row.get("currency_override"),
            "duration_quantity_json": override_row.get("duration_quantity_json"),
            "approval_required_override": override_row.get("approval_required_override"),
            "hr_notes": override_row.get("hr_notes"),
        }

    merged = merge_benefit_rule_for_effective_layer(rule, override_row)
    meta_e = _parse_meta(merged)
    force_excl = bool(meta_e.get("hr_force_excluded"))
    effective = {
        "benefit_rule_id": rid,
        "benefit_key": bk,
        "amount_value": merged.get("amount_value"),
        "amount_unit": merged.get("amount_unit"),
        "currency": merged.get("currency"),
        "frequency": merged.get("frequency"),
        "calc_type": merged.get("calc_type"),
        "approval_required": bool(meta_e.get("approval_required")),
        "included": not force_excl and meta_e.get("allowed", True) is not False,
        "hr_notes_effective": (override_row or {}).get("hr_notes"),
    }
    return {
        "benefit_rule_id": str(rid) if rid is not None else None,
        "benefit_key": bk,
        TRACE_BASELINE: baseline,
        TRACE_HR_OVERRIDE: hr_layer,
        TRACE_EFFECTIVE: effective,
    }


def merge_benefit_rule_for_effective_layer(
    rule: Dict[str, Any],
    override_row: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Deep-enough copy of a benefit rule with HR overrides applied (for resolution / comparison)."""
    out = copy.deepcopy(rule) if rule else {}
    meta = _parse_meta(out)

    o = _normalize_override_row(override_row) if override_row else None
    if not o:
        out["metadata_json"] = meta
        return out

    vis = o.get("service_visibility")
    if vis == "force_excluded":
        meta["hr_force_excluded"] = True
        meta["allowed"] = False
        out["amount_value"] = None
        out["calc_type"] = out.get("calc_type") or "other"
    elif vis == "force_included":
        meta.pop("hr_force_excluded", None)
        meta["allowed"] = True

    if vis != "force_excluded":
        if o.get("amount_value_override") is not None:
            try:
                out["amount_value"] = float(o["amount_value_override"])
            except (TypeError, ValueError):
                out["amount_value"] = o["amount_value_override"]
        if o.get("amount_unit_override"):
            out["amount_unit"] = str(o["amount_unit_override"]).strip()
        if o.get("currency_override"):
            out["currency"] = str(o["currency_override"]).strip()

    dqj = o.get("duration_quantity_json")
    if isinstance(dqj, dict) and dqj and vis != "force_excluded":
        meta["hr_duration_quantity"] = dqj
        qty = dqj.get("quantity")
        unit = str(dqj.get("unit") or "").lower()
        if qty is not None and unit and "day" in unit:
            try:
                out["amount_value"] = float(qty)
            except (TypeError, ValueError):
                out["amount_value"] = qty
            out["amount_unit"] = "days"
            ct = (out.get("calc_type") or "").strip()
            if not ct or ct == "other":
                out["calc_type"] = "unit_cap"

    ar = o.get("approval_required_override")
    if ar is not None:
        meta["approval_required"] = bool(ar)

    out["metadata_json"] = meta
    return out


def force_excluded_by_hr_override(override_row: Optional[Dict[str, Any]]) -> bool:
    o = _normalize_override_row(override_row)
    return bool(o and o.get("service_visibility") == "force_excluded")


def merge_benefit_rules_for_effective_readiness(
    db: Any,
    policy_version_id: str,
    benefit_rules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Benefit rules merged for policy_readiness / comparison slices (uses DB overrides if present)."""
    ovs = _safe_list_overrides(db, policy_version_id)
    by_id = index_hr_overrides_by_benefit_rule_id(ovs)
    out: List[Dict[str, Any]] = []
    for r in benefit_rules:
        rid = r.get("id")
        merged = merge_benefit_rule_for_effective_layer(r, by_id.get(str(rid)) if rid else None)
        out.append(merged)
    return out


def merge_benefit_rules_for_comparison_engine(
    db: Any,
    policy_version_id: str,
    benefit_rules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Alias: comparison engine uses same merge as readiness."""
    return merge_benefit_rules_for_effective_readiness(db, policy_version_id, benefit_rules)


def build_effective_entitlement_preview(
    db: Any,
    policy_version_id: str,
    benefit_rules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """List of value traces for HR review UI."""
    ovs = _safe_list_overrides(db, policy_version_id)
    by_id = index_hr_overrides_by_benefit_rule_id(ovs)
    return [
        compute_entitlement_value_trace(r, by_id.get(str(r.get("id"))) if r.get("id") else None)
        for r in benefit_rules
    ]


def _safe_list_overrides(db: Any, policy_version_id: str) -> List[Dict[str, Any]]:
    try:
        fn = getattr(db, "list_hr_benefit_rule_overrides", None)
        if callable(fn):
            return list(fn(str(policy_version_id)) or [])
    except Exception:
        pass
    return []


def load_merged_benefit_rule_for_resolution(
    db: Any,
    policy_version_id: str,
    rule: Dict[str, Any],
    overrides_by_rule_id: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Return (merged_rule, value_trace) for one rule during assignment resolution."""
    rid = rule.get("id")
    by_id = overrides_by_rule_id
    if by_id is None:
        by_id = index_hr_overrides_by_benefit_rule_id(_safe_list_overrides(db, policy_version_id))
    ov = by_id.get(str(rid)) if rid is not None else None
    merged = merge_benefit_rule_for_effective_layer(rule, ov)
    trace = compute_entitlement_value_trace(rule, ov)
    return merged, trace
