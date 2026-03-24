"""
When a company has a published Compensation & Allowance matrix but no legacy
company_policies / policy_versions row, employee HR Policy + policy-budget should
still resolve so they stay in sync with GET /api/employee/policy-config.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from .policy_config_targeting import normalize_assignment_type, normalize_family_status, row_matches_targeting

log = logging.getLogger(__name__)

CONFIG_KEY = "compensation_allowance"


def find_published_matrix_version(db: Any, company_ids: List[str]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """First candidate company with a published policy_config matrix row."""
    for cid in company_ids:
        if not cid:
            continue
        try:
            pub = db.get_latest_published_policy_config_version(str(cid), CONFIG_KEY)
        except Exception as exc:
            log.warning("matrix bridge get_latest_published failed company_id=%s exc=%s", cid, exc)
            pub = None
        if pub:
            return str(cid), pub
    return None, None


def _matrix_row_to_pack_benefit(row: Dict[str, Any]) -> Dict[str, Any]:
    """Align with PackBenefitRow + caps_from_resolved_benefits."""
    bk = str(row.get("benefit_key") or "").strip()
    covered = bool(row.get("covered"))
    vt = str(row.get("value_type") or "").lower()
    amount = row.get("amount_value")
    pct = row.get("percentage_value")
    cur = row.get("currency_code") or "USD"
    freq = str(row.get("unit_frequency") or "")
    notes = row.get("notes")
    cap_rule = row.get("cap_rule_json") if isinstance(row.get("cap_rule_json"), dict) else {}
    cond = row.get("conditions_json") if isinstance(row.get("conditions_json"), dict) else {}

    max_v = None
    std_v = None
    if vt == "currency" and amount is not None:
        try:
            fv = float(amount)
            if fv > 0:
                max_v = fv
                std_v = fv
        except (TypeError, ValueError):
            pass
    elif vt == "percentage" and pct is not None:
        try:
            max_v = float(pct)
        except (TypeError, ValueError):
            pass

    condition_summary = (notes or "").strip() or None
    if not condition_summary and cond:
        condition_summary = json.dumps(cond, ensure_ascii=False)[:500]

    exclusions: List[Dict[str, str]] = []
    if not covered:
        exclusions.append(
            {
                "domain": "compensation_matrix",
                "description": "Not covered under your employer's published compensation & allowance policy for your assignment profile.",
            }
        )

    return {
        "benefit_key": bk,
        "included": covered,
        "min_value": None,
        "standard_value": std_v,
        "max_value": max_v,
        "currency": cur,
        "amount_unit": None,
        "frequency": freq,
        "approval_required": bool(cap_rule.get("approval_required")),
        "evidence_required_json": [],
        "exclusions_json": exclusions,
        "condition_summary": condition_summary,
    }


def build_matrix_assignment_package(
    db: Any,
    *,
    company_id: str,
    pub_version: Dict[str, Any],
    assignment_type_ctx: Any,
    family_status_ctx: Any,
    company_name: Optional[str],
    assignment_id: str,
    case_id: Optional[str],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Returns (resolved_out, comparison_readiness_precalc) for _finalize_employee_policy_resolution.
    """
    vid = str(pub_version.get("id") or "").strip()
    raw_benefits: List[Dict[str, Any]] = []
    if vid:
        try:
            raw_benefits = db.list_policy_config_benefits(vid)
        except Exception as exc:
            log.warning("matrix bridge list_policy_config_benefits failed version_id=%s exc=%s", vid, exc)
            raw_benefits = []

    at_m = normalize_assignment_type(assignment_type_ctx)
    fs_m = normalize_family_status(family_status_ctx)

    pack_benefits: List[Dict[str, Any]] = []
    for b in raw_benefits:
        if not b.get("is_active", True):
            continue
        if not row_matches_targeting(b, at_m, fs_m, strict_context=True):
            continue
        pack_benefits.append(_matrix_row_to_pack_benefit(b))

    if not pack_benefits:
        # Published matrix exists but nothing applies to this profile — still better than "no policy".
        log.info(
            "matrix bridge no matching rows company_id=%s version_id=%s assignment_id=%s",
            company_id,
            vid,
            assignment_id,
        )

    from .policy_adapter import caps_from_resolved_benefits

    budget = caps_from_resolved_benefits(pack_benefits)
    caps = budget.get("caps") or {}
    has_numeric_cap = any(isinstance(v, (int, float)) and v > 0 for v in caps.values())
    comparison_readiness_precalc = {
        "comparison_ready": has_numeric_cap,
        "comparison_blockers": [] if has_numeric_cap else ["MATRIX_NO_SERVICE_CATEGORY_CAPS"],
        "partial_numeric_coverage": has_numeric_cap,
    }

    eff = pub_version.get("effective_date")
    eff_s = str(eff)[:10] if eff is not None else None
    vnum = int(pub_version.get("version_number") or 0)

    resolved = {
        "has_policy": True,
        "company_id": company_id,
        "policy_id": f"policy_config_matrix:{vid}",
        "version_id": None,
        "assignment_id": assignment_id,
        "case_id": case_id,
        "policy": {
            "id": f"policy_config_matrix:{vid}",
            "title": "Compensation & allowance (published)",
            "version": vnum,
            "effective_date": eff_s,
            "company_name": company_name,
        },
        "benefits": pack_benefits,
        "exclusions": [],
        "resolved_at": pub_version.get("published_at"),
        "resolution_context": {
            "assignment_type": assignment_type_ctx,
            "family_status": family_status_ctx,
            "source": "policy_config_matrix",
        },
    }
    return resolved, comparison_readiness_precalc
