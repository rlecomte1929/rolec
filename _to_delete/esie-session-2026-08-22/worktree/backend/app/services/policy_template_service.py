"""
Unified, versioned HR policy template schema + service (N12 / AIQ-852).

Historically four uncoordinated template systems existed:
  1. ``POLICY_TEMPLATES`` dict          — policy_config_templates.py (comp/allowance matrix starter)
  2. ``_TIER_CAPS`` dict                — policy_starter_templates.py (5 service caps x 3 tiers)
  3. ``benefits_templates`` table       — read in routers/policy_templates.py (out-of-band prod table)
  4. canonical LTA template (35 fields) — policy_canonical_lta_template.py + default_policy_templates
                                          table (snapshot_json) consumed by the W4 gap-fill.

This module is the single source of truth that unifies them: one Pydantic
``PolicyTemplateSchema`` and one ``PolicyTemplateService``. Templates are kept
as Python data so they ship with the image and can be exercised by unit tests
without database IO (same philosophy already used by policy_config_templates.py).
A migration (``policy_templates_v2`` + ``policy_template_benefits``) mirrors this
registry into the database for SQL consumers and version archiving.

The four legacy systems are NOT removed — they remain in place, marked
deprecated, until a follow-up cleanup task retires them after validation.

Numbers here are reasonable-default placeholders, not legal advice. The LTA tiers
are ported from the curated ``_TIER_CAPS``/``POLICY_TEMPLATES`` values; the STA
tiers are new platform placeholders (lower ``field_confidence``) for HR to tune.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .policy_canonical_lta_template import (
    CANONICAL_LTA_TEMPLATE_FIELDS,
    get_canonical_lta_field,
)

# --- Canonical schema -------------------------------------------------------

PolicyType = Literal["LTA", "STA", "commuter"]
GenerosityTier = Literal["conservative", "standard", "premium"]

SCHEMA_VERSION = "1.0.0"  # semver — replaces free-text "canonical_lta_template_v1" / "v2.1"


class TemplateBenefit(BaseModel):
    """One benefit line within a policy template."""

    benefit_key: str
    default_value: Optional[float] = None  # numeric cap; None for narrative-only fields
    value_type: str  # amount | duration | quantity | percentage | narrative | external_reference
    is_required: bool = False
    field_confidence: float = Field(ge=0.0, le=1.0)


class PolicyTemplateSchema(BaseModel):
    """A single versioned policy template (one policy_type x generosity_tier)."""

    template_id: str
    version: str = SCHEMA_VERSION
    policy_type: PolicyType
    generosity_tier: GenerosityTier
    geography: Optional[str] = None
    industry: Optional[str] = None
    benefits: List[TemplateBenefit]


# --- Tier numeric defaults (USD), keyed by benefit-taxonomy key -------------
#
# LTA defaults port the curated caps from _TIER_CAPS (immigration / temporary_housing /
# schooling / shipment) plus sensible housing & movers caps drawn from the
# POLICY_TEMPLATES comp/allowance baseline. These feed the W4 gap-fill.
_LTA_TIER_DEFAULTS: Dict[str, Dict[str, float]] = {
    "conservative": {
        "immigration": 2500,
        "temporary_housing": 3500,
        "schooling": 8000,
        "shipment": 5000,
        "housing": 2500,
        "movers": 5000,
    },
    "standard": {
        "immigration": 4000,
        "temporary_housing": 5500,
        "schooling": 15000,
        "shipment": 10000,
        "housing": 3500,
        "movers": 10000,
    },
    "premium": {
        "immigration": 6500,
        "temporary_housing": 8500,
        "schooling": 25000,
        "shipment": 18000,
        "housing": 5000,
        "movers": 18000,
    },
}

# --- Starter-template caps (USD), keyed by SERVICE then tier -----------------
# [TPL-1/AIQ-1131] Ported VERBATIM from the retired
# ``policy_starter_templates._TIER_CAPS`` so the starter-template initializer
# (POST /api/company/policy-templates/initialize) routes through this unified
# service. NOTE: this is keyed by SERVICE (visa_support / temporary_housing /
# home_search / school_search / household_goods_shipment) — DISTINCT from
# ``_LTA_TIER_DEFAULTS`` above, which is keyed by benefit-taxonomy and has NO
# ``home_search``. Do not conflate the two: reusing _LTA_TIER_DEFAULTS here would
# silently drop the home_search cap.
_STARTER_TEMPLATE_CAPS: Dict[str, Dict[str, float]] = {
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

# STA = short-term assignment (typically < 12 months): no family relocation,
# no household-goods shipment, no school search; temporary housing dominates.
# NEW placeholder content — lower field_confidence so HR knows to tune it.
_STA_FIELD_KEYS = (
    "work_permits_and_visas",   # immigration
    "medical_exam_support",     # medical
    "travel_to_host",           # transport
    "temporary_living_outbound",  # temporary_housing (primary STA cost)
    "settling_in_support",      # settling_in_allowance
    "host_transportation",      # transport (local)
    "mobility_premium",         # percentage
    "home_leave",               # quantity
    "tax_briefing",             # tax
    "return_travel",            # transport (home)
    "approval_authority_matrix",  # governance
)

_STA_TIER_DEFAULTS: Dict[str, Dict[str, float]] = {
    "conservative": {"immigration": 2000, "temporary_housing": 6000, "transport": 1200},
    "standard": {"immigration": 3000, "temporary_housing": 9000, "transport": 2000},
    "premium": {"immigration": 4500, "temporary_housing": 14000, "transport": 3500},
}

_LTA_FIELD_CONFIDENCE = 0.9
_STA_FIELD_CONFIDENCE = 0.5


def _benefit_from_field(field, tier_defaults: Dict[str, float], confidence: float) -> TemplateBenefit:
    tax = field.maps_to_benefit_taxonomy_key
    return TemplateBenefit(
        benefit_key=field.key,
        default_value=tier_defaults.get(tax) if tax else None,
        value_type=field.value_type.value,
        is_required=field.drives_comparison,
        field_confidence=confidence,
    )


def _build_lta(tier: GenerosityTier) -> PolicyTemplateSchema:
    defaults = _LTA_TIER_DEFAULTS[tier]
    benefits = [
        _benefit_from_field(f, defaults, _LTA_FIELD_CONFIDENCE)
        for f in CANONICAL_LTA_TEMPLATE_FIELDS
    ]
    return PolicyTemplateSchema(
        template_id=f"LTA_{tier}",
        policy_type="LTA",
        generosity_tier=tier,
        benefits=benefits,
    )


def _build_sta(tier: GenerosityTier) -> PolicyTemplateSchema:
    defaults = _STA_TIER_DEFAULTS[tier]
    benefits: List[TemplateBenefit] = []
    for key in _STA_FIELD_KEYS:
        field = get_canonical_lta_field(key)
        if field is None:
            continue
        benefits.append(_benefit_from_field(field, defaults, _STA_FIELD_CONFIDENCE))
    return PolicyTemplateSchema(
        template_id=f"STA_{tier}",
        policy_type="STA",
        generosity_tier=tier,
        benefits=benefits,
    )


def _build_registry() -> Dict[str, PolicyTemplateSchema]:
    registry: Dict[str, PolicyTemplateSchema] = {}
    for tier in ("conservative", "standard", "premium"):
        lta = _build_lta(tier)  # type: ignore[arg-type]
        sta = _build_sta(tier)  # type: ignore[arg-type]
        registry[lta.template_id] = lta
        registry[sta.template_id] = sta
    return registry


# Built once at import — immutable platform data.
_REGISTRY: Dict[str, PolicyTemplateSchema] = _build_registry()


# --- Benchmark reference library (N12-followup-a / AIQ-889) ------------------
#
# Ported from the out-of-band ``benefits_templates`` prod table (42 rows = 14
# categories x 3 generosity tiers), retiring the 4th legacy template system.
# This is a CATEGORY-level benchmark *reference* (what a conservative/standard/
# premium policy looks like per spend category, sourced from AIRINC/Mercer/ECA/
# KPMG/CIGNA) — distinct from the granular per-benefit LTA/STA operational
# templates above. Kept here as deterministic data (no DB IO, same philosophy as
# the registry); migration 20260618100000 mirrors it into policy_templates_v2
# (policy_type='benchmark_reference'). Currency is EUR (NOT the USD of the
# LTA/STA registry) — preserved, never coerced.
BENCHMARK_TIER_ORDER: Dict[str, int] = {"Conservative": 1, "Standard": 2, "Premium": 3}
BENCHMARK_CURRENCY = "EUR"

# (code, display_name, unit, benchmark_source, conservative, standard, premium)
_BENCHMARK_CATEGORIES: List[tuple] = [
    ("CAT-01", "Housing & Accommodation", "month", "AIRINC 2025 European upper quartile", 1800, 2800, 4500),
    ("CAT-02", "Transportation", "month", "ECA International 2024 median (car lease option)", 400, 750, 1400),
    ("CAT-03", "International Schooling", "month", "AIRINC 2025 state school contribution, Europe", 800, 1800, 4000),
    ("CAT-04", "Cost of Living Adjustment", "month", "Mercer 2024 COLA upper range, high-cost city", 400, 700, 1200),
    ("CAT-05", "Healthcare & Wellbeing", "month", "CIGNA Global 2025 premium plan + dental + mental health", 250, 450, 800),
    ("CAT-06", "Tax & Social Security", "year", "KPMG 2024 full tax equalisation advisory", 2500, 4500, 9000),
    ("CAT-07", "Travel & Home Leave", "year", "AIRINC 2025 two economy+ return flights per year", 900, 3000, 8000),
    ("CAT-08", "Relocation Assistance", "per_move", "Mercer 2024 managed move + lump-sum, European executive", 8000, 15000, 28000),
    ("CAT-09", "Settling-In & Orientation", "per_move", "ECA International 2024 standard DSP, 5 days + admin support", 1500, 3000, 6000),
    ("CAT-10", "Spouse & Family Support", "per_move", "AIRINC 2025 full partner career coaching + integration", 1000, 3500, 8000),
    ("CAT-11", "Assignment Allowances", "month", "ECA International 2024 standard foreign service premium", 300, 700, 1500),
    ("CAT-12", "End of Assignment", "per_move", "Mercer 2024 repatriation median", 5000, 10000, 20000),
    ("CAT-13", "Governance & Process", "year", "ReloPass internal standard (policy management + HR support)", 500, 1000, 2000),
    ("CAT-14", "Legal & Compliance", "per_move", "KPMG 2024 full immigration + compliance advisory", 2000, 4000, 8000),
]


# --- Service ----------------------------------------------------------------


class PolicyTemplateService:
    """Read access to the unified, versioned policy template registry.

    The default template used by the W4 gap-fill (``get_default_benefits``) is the
    standard-tier LTA template, matching the prior platform-default behaviour.
    """

    DEFAULT_TEMPLATE_ID = "LTA_standard"

    def __init__(self, registry: Optional[Dict[str, PolicyTemplateSchema]] = None):
        self._registry = registry if registry is not None else _REGISTRY

    @staticmethod
    def get_starter_template_caps() -> Dict[str, Dict[str, float]]:
        """Per-service numeric caps for the starter templates, keyed by tier then
        service (visa_support / temporary_housing / home_search / school_search /
        household_goods_shipment). Ported verbatim from the retired ``_TIER_CAPS``
        dict; consumed by ``build_starter_template_benefit_rows()``. Returns a fresh
        copy so callers cannot mutate the module constant. [TPL-1/AIQ-1131]"""
        return {tier: dict(caps) for tier, caps in _STARTER_TEMPLATE_CAPS.items()}

    # ------------------------------------------------------------------
    # Comp & Allowance matrix starter templates [TPL-2/AIQ-1132]
    #
    # The Conservative / Standard / Premium baseline rows for the Comp &
    # Allowance MATRIX namespace. Data lives in policy_config_templates
    # (COMP_ALLOWANCE_TEMPLATES); the logic below was moved verbatim off the
    # retired module-level list_templates / get_template / expand_template_rows
    # so this service is the single template entry point. Output is byte-identical
    # to the retired functions (proven by the golden-equivalence test). This is a
    # distinct shape from the typed PolicyTemplateSchema above (LTA/STA), so the
    # methods are namespaced (`..._comp_allowance_...`) rather than overloading
    # get_template / list_templates.
    # ------------------------------------------------------------------

    @staticmethod
    def list_comp_allowance_templates() -> List[Dict[str, Any]]:
        """Metadata for the picker UI — no row data, fast to serialize."""
        from .policy_config_templates import COMP_ALLOWANCE_TEMPLATES

        return [
            {
                "key": v["key"],
                "label": v["label"],
                "description": v["description"],
            }
            for v in COMP_ALLOWANCE_TEMPLATES.values()
        ]

    @staticmethod
    def get_comp_allowance_template(key: str) -> Optional[Dict[str, Any]]:
        from .policy_config_templates import COMP_ALLOWANCE_TEMPLATES

        return COMP_ALLOWANCE_TEMPLATES.get(str(key).strip().lower())

    @staticmethod
    def expand_comp_allowance_rows(template_key: str) -> List[Dict[str, Any]]:
        """
        Expand a template into a list of concrete benefit rows ready to
        insert into a draft. Tiered rows become N rows (one per
        employee level). Display order follows the declaration order; the
        matrix service will re-sort by category + display_order on read.

        Raises KeyError if the template key is unknown.
        """
        from .policy_config_targeting import EMPLOYEE_LEVELS

        tpl = PolicyTemplateService.get_comp_allowance_template(template_key)
        if tpl is None:
            raise KeyError(f"unknown_template:{template_key}")
        rows: List[Dict[str, Any]] = []
        order = 0
        for src in tpl["rows"]:
            order += 10
            base = {
                "benefit_key": src["benefit_key"],
                "category": src["category"],
                "covered": bool(src.get("covered", False)),
                "value_type": src.get("value_type", "none"),
                "currency_code": src.get("currency_code"),
                "percentage_value": src.get("percentage"),
                "unit_frequency": src.get("unit_frequency", "one_time"),
                "notes": src.get("notes"),
                "cap_rule_json": {},
                "conditions_json": {},
                "assignment_types": [],
                "family_statuses": [],
                "is_active": True,
                "display_order": order,
            }
            amounts_by_level = src.get("amounts_by_level")
            if isinstance(amounts_by_level, dict) and amounts_by_level:
                # Emit one row per level so HR can tier caps from day one.
                # Any level missing from the map falls back to 0 and is
                # skipped rather than silently written as a zero cap — the
                # row should really declare all levels (see _tiered_amounts).
                for level in sorted(EMPLOYEE_LEVELS):
                    amount = amounts_by_level.get(level)
                    if amount is None:
                        continue
                    out = dict(base)
                    out["amount_value"] = float(amount)
                    out["employee_levels"] = [level]
                    rows.append(out)
            else:
                out = dict(base)
                if "amount" in src:
                    out["amount_value"] = float(src["amount"])
                elif "percentage" in src:
                    out["percentage_value"] = float(src["percentage"])
                else:
                    out["amount_value"] = None
                out["employee_levels"] = []
                rows.append(out)
        return rows

    def get_template(
        self,
        policy_type: PolicyType,
        generosity_tier: GenerosityTier,
        geography: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> PolicyTemplateSchema:
        """Return the template for a policy type + tier.

        ``geography`` / ``industry`` are accepted for forward-compatibility (variants
        are not defined yet) and currently do not change the result.
        """
        template_id = f"{policy_type}_{generosity_tier}"
        template = self._registry.get(template_id)
        if template is None:
            raise KeyError(f"No policy template for {template_id!r}")
        return template

    def list_templates(self) -> List[PolicyTemplateSchema]:
        return list(self._registry.values())

    # --- platform-default template (TPL-3: replaces default_policy_templates) -----
    @staticmethod
    def get_default_template_record() -> Dict[str, Any]:
        """The platform-default policy template record (id, metadata, snapshot_json).

        Replaces ``db.get_default_policy_template`` / ``list_default_policy_templates``
        — the table held exactly this one seeded row. Code-backed now (TPL-3).
        """
        from .default_policy_template_snapshot import get_platform_default_template
        return get_platform_default_template()

    def get_template_snapshot(self, template_id: Optional[str] = None) -> Dict[str, Any]:
        """The platform-default ``snapshot_json`` (benefit_rules, effectiveDate, caps…).

        ``template_id`` is accepted for call-site compatibility but ignored: there is a
        single platform default. Mirrors the old ``snapshot_json`` shape exactly.
        """
        return self.get_default_template_record()["snapshot_json"]

    def build_admin_template_list(self) -> List[Dict[str, Any]]:
        """Admin template list (the old ``GET /api/admin/policies/templates`` shape).

        The legacy table returned its single default row; preserve that.
        """
        return [self.get_default_template_record()]

    def get_benchmark_library(self) -> List[Dict[str, object]]:
        """Category-level benchmark reference library (AIQ-889), grouped by tier.

        Returns 3 tiers (Conservative/Standard/Premium), each with all 14 spend
        categories and their EUR benchmark caps. Shape matches the
        /api/policy/templates response (replaces the direct benefits_templates read).
        """
        # tuple layout: (code, display_name, unit, source, conservative, standard, premium)
        cap_pos = {"Conservative": 0, "Standard": 1, "Premium": 2}
        tiers: List[Dict[str, object]] = []
        for tier_name, tier_order in sorted(BENCHMARK_TIER_ORDER.items(), key=lambda kv: kv[1]):
            pos = cap_pos[tier_name]
            categories = [
                {
                    "category_id": code,  # stable category code (service is DB-free; was a uuid in the legacy table)
                    "code": code,
                    "display_name": display_name,
                    "cap_value": float(caps[pos]),
                    "cap_unit": unit,
                    "cap_currency": BENCHMARK_CURRENCY,
                    "benchmark_source": source,
                }
                for code, display_name, unit, source, *caps in _BENCHMARK_CATEGORIES
            ]
            tiers.append({"tier": tier_name, "tier_order": tier_order, "categories": categories})
        return tiers

    def get_default_benefits(self, template_id: Optional[str] = None) -> Dict[str, Dict[str, object]]:
        """Gap-fill defaults keyed by benefit-taxonomy key.

        Backward-compatible with the W4 ``get_template_defaults`` contract: each value
        is a ``benefit_rules``-shaped dict (``benefit_key``, ``benefit_category``,
        ``calc_type``, ``amount_value``, ``amount_unit``, ``currency``). Only benefits
        that carry a numeric default and map to a taxonomy key are returned.
        """
        tid = template_id or self.DEFAULT_TEMPLATE_ID
        template = self._registry.get(tid)
        if template is None:
            return {}
        out: Dict[str, Dict[str, object]] = {}
        for benefit in template.benefits:
            if benefit.default_value is None:
                continue
            field = get_canonical_lta_field(benefit.benefit_key)
            tax = field.maps_to_benefit_taxonomy_key if field else None
            if not tax:
                continue
            is_monthly = tax in ("temporary_housing", "housing")
            out[tax] = {
                "benefit_key": tax,
                "benefit_category": tax,
                "calc_type": "unit_cap" if is_monthly else "flat_amount",
                "amount_value": benefit.default_value,
                "amount_unit": "per_month" if is_monthly else "lump_sum",
                "currency": "USD",
            }
        return out


__all__ = [
    "GenerosityTier",
    "PolicyTemplateSchema",
    "PolicyTemplateService",
    "PolicyType",
    "SCHEMA_VERSION",
    "TemplateBenefit",
]
