"""
Platform starter policy templates (conservative / standard / premium).

Structured baselines mapped to the canonical entitlement model (see policy_entitlement_model).
Layer-2 rows use legacy benefit_key; metadata_json carries service_key, coverage, limits,
comparison_readiness, and employee_visible_value.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple

from .policy_document_intake import SCOPE_LONG_TERM
from .policy_entitlement_model import (
    CANONICAL_SERVICE_TO_CATEGORY,
    CANONICAL_SERVICE_TO_LEGACY_BENEFIT_KEY,
    ComparisonReadiness,
    CoverageStatus,
    EntitlementCategory,
    PublishabilityState,
    RuleStrength,
)
from .policy_taxonomy import get_benefit_meta, resolve_theme

StarterTemplateKey = Literal["conservative", "standard", "premium"]

STARTER_TEMPLATE_KEYS: Tuple[str, ...] = ("conservative", "standard", "premium")

STARTER_TEMPLATE_DISCLAIMER = (
    "This baseline is a starting point only. It does not reflect your company’s approved policy "
    "until HR reviews, customizes, and publishes a version."
)

# Minimum product services (canonical) for v1 — amounts are USD illustrative caps.
_SERVICE_ORDER: Tuple[str, ...] = (
    "visa_support",
    "temporary_housing",
    "home_search",
    "school_search",
    "household_goods_shipment",
)

# template_key -> per-service numeric cap (USD or months where noted)
_TIER_CAPS: Dict[str, Dict[str, float]] = {
    "conservative": {
        "visa_support": 2500,
        "temporary_housing": 3500,
        "home_search": 1500,
        "school_search": 8000,
        "household_goods_shipment": 5000,
    },
    "standard": {
        "visa_support": 4000,
        "temporary_housing": 5500,
        "home_search": 2500,
        "school_search": 15000,
        "household_goods_shipment": 10000,
    },
    "premium": {
        "visa_support": 6500,
        "temporary_housing": 8500,
        "home_search": 4000,
        "school_search": 25000,
        "household_goods_shipment": 18000,
    },
}


def list_starter_template_keys() -> List[str]:
    return list(STARTER_TEMPLATE_KEYS)


def is_valid_starter_template_key(key: str) -> bool:
    return key in STARTER_TEMPLATE_KEYS


def starter_policy_document_stub(template_key: str) -> Dict[str, Any]:
    return {
        "id": None,
        "company_id": None,
        "processing_status": "complete",
        "detected_document_type": "starter_template",
        "detected_policy_scope": SCOPE_LONG_TERM,
        "extracted_metadata": {"starter_template_key": template_key, "kind": "platform_starter_baseline"},
        "filename": f"starter_template_{template_key}",
        "version_label": "1.0-template",
        "effective_date": None,
    }


def _employee_visible(
    *,
    service_key: str,
    label: str,
    summary: str,
    numeric_max: Optional[float],
    currency: str,
    unit: Optional[str],
    frequency: str,
) -> Dict[str, Any]:
    ev: Dict[str, Any] = {
        "label": label,
        "summary_text": summary,
        "currency": currency,
        "frequency": frequency,
    }
    if numeric_max is not None:
        ev["numeric_max"] = numeric_max
    if unit:
        ev["unit"] = unit
    return ev


def _canonical_meta(
    *,
    template_key: str,
    service_key: str,
    coverage_status: str,
    rule_strength: str,
    comparison_readiness: str,
    employee_visible_value: Dict[str, Any],
    comparison_ready_structure: bool,
) -> Dict[str, Any]:
    cat = CANONICAL_SERVICE_TO_CATEGORY.get(service_key) or EntitlementCategory.MISC
    category_value = cat.value
    return {
        "canonical_entitlement": {
            "service_key": service_key,
            "category": category_value,
            "coverage_status": coverage_status,
            "rule_strength": rule_strength,
            "comparison_readiness": comparison_readiness,
            "employee_visible_value": employee_visible_value,
            "applicability": {
                "assignment_types": ["LTA", "STA"],
                "family_status_terms": [],
            },
            "publishability": PublishabilityState.ELIGIBLE_UNDER_GATE.value
            if comparison_ready_structure
            else PublishabilityState.DRAFT_ONLY.value,
        },
        "template_baseline": True,
        "template_key": template_key,
        "not_company_approved_until_published": True,
    }


def build_starter_template_benefit_rows(
    template_key: StarterTemplateKey,
    *,
    policy_version_id: str,
    comparison_ready_structure: bool = True,
) -> List[Dict[str, Any]]:
    """
    Rows suitable for insert_policy_benefit_rule (includes policy_version_id, metadata_json).
    """
    caps = _TIER_CAPS.get(template_key) or _TIER_CAPS["standard"]
    rows: List[Dict[str, Any]] = []

    for sk in _SERVICE_ORDER:
        legacy_bk = CANONICAL_SERVICE_TO_LEGACY_BENEFIT_KEY.get(sk)
        if not legacy_bk:
            continue
        meta_benefit = get_benefit_meta(legacy_bk)
        group = meta_benefit.get("group") or "misc"
        benefit_category = resolve_theme(legacy_bk, group)
        cap = float(caps.get(sk, 0))

        if sk == "temporary_housing":
            calc_type = "unit_cap" if comparison_ready_structure else "other"
            amount_unit = "per_month" if comparison_ready_structure else None
            label = "Temporary housing"
            summary = (
                f"Up to USD {cap:,.0f} per month temporary housing support (baseline)."
                if comparison_ready_structure
                else "Temporary housing may be available subject to policy terms (baseline narrative)."
            )
        else:
            calc_type = "flat_amount" if comparison_ready_structure else "other"
            amount_unit = "lump_sum" if comparison_ready_structure else None
            labels = {
                "visa_support": "Visa & immigration support",
                "home_search": "Home search assistance",
                "school_search": "School search / education support",
                "household_goods_shipment": "Household goods shipment",
            }
            label = labels.get(sk, sk)
            summary = (
                f"Up to USD {cap:,.0f} toward {label.lower()} (baseline)."
                if comparison_ready_structure
                else f"{label} may be available per policy (baseline narrative)."
            )

        amount_value = cap if comparison_ready_structure else None
        currency = "USD"

        cov = CoverageStatus.INCLUDED.value
        if comparison_ready_structure:
            cmp_r = ComparisonReadiness.READY.value
            r_strength = RuleStrength.COMPARISON_READY.value
        else:
            cmp_r = ComparisonReadiness.PARTIAL.value
            r_strength = RuleStrength.INFORMATIONAL.value

        ev = _employee_visible(
            service_key=sk,
            label=label,
            summary=summary,
            numeric_max=amount_value,
            currency=currency,
            unit=amount_unit,
            frequency="per_assignment",
        )
        metadata_json = _canonical_meta(
            template_key=template_key,
            service_key=sk,
            coverage_status=cov,
            rule_strength=r_strength,
            comparison_readiness=cmp_r,
            employee_visible_value=ev,
            comparison_ready_structure=comparison_ready_structure,
        )

        rows.append(
            {
                "policy_version_id": policy_version_id,
                "benefit_key": legacy_bk,
                "benefit_category": benefit_category,
                "calc_type": calc_type,
                "amount_value": amount_value,
                "amount_unit": amount_unit,
                "currency": currency,
                "frequency": "per_assignment",
                "description": summary[:2000],
                "raw_text": summary,
                "confidence": 1.0 if comparison_ready_structure else 0.75,
                "metadata_json": metadata_json,
                "auto_generated": True,
                "review_status": "pending",
            }
        )

    return rows


__all__ = [
    "STARTER_TEMPLATE_DISCLAIMER",
    "STARTER_TEMPLATE_KEYS",
    "StarterTemplateKey",
    "build_starter_template_benefit_rows",
    "is_valid_starter_template_key",
    "list_starter_template_keys",
    "starter_policy_document_stub",
]
