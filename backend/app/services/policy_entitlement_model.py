"""
Canonical entitlement model for ReloPass (HR review, overrides, employee read, comparison).

This module is the **contract** for how a single entitlement *rule* should be represented
across pipelines. It does not replace `policy_benefit_rules` / `policy_exclusions` (Layer 2);
it classifies and structures what those rows (and draft-only candidates) *mean* for:

- HR review of extracted policy content
- HR overrides (notes, strength, visibility)
- Employee read-only entitlements (subset of fields, gated by publish + strength)
- Service / envelope comparison (requires comparison-ready signal + limits where needed)
- Partial / informational rules when numeric caps are absent

See ``docs/policy/canonical-entitlement-model.md`` for mappings to normalization draft,
Layer 2, and employee resolution payloads.

Alignment:
- **Legacy Layer-2** continues to use ``benefit_key`` from ``policy_taxonomy`` / ``BENEFIT_TAXONOMY``.
- **Canonical service_key** (below) is the ReloPass product vocabulary for services UI and
  comparison; map via ``CANONICAL_SERVICE_TO_LEGACY_BENEFIT_KEY``.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, TypedDict

# ---------------------------------------------------------------------------
# Categories (HR grouping / navigation; maps to policy themes where possible)
# ---------------------------------------------------------------------------


class EntitlementCategory(str, Enum):
    """Stable category for entitlement rules (UI + analytics)."""

    IMMIGRATION = "immigration"
    HOUSING = "housing"
    RELOCATION_LOGISTICS = "relocation_logistics"
    EDUCATION = "education"
    TAX = "tax"
    INTEGRATION = "integration"
    FAMILY = "family"
    TRAVEL = "travel"
    COMPENSATION = "compensation"
    HEALTH = "health"
    COMPLIANCE = "compliance"
    MISC = "misc"


ENTITLEMENT_CATEGORIES: FrozenSet[str] = frozenset(m.value for m in EntitlementCategory)


# ---------------------------------------------------------------------------
# Canonical service keys (minimum product taxonomy; extend over time)
# ---------------------------------------------------------------------------


class CanonicalServiceKey(str, Enum):
    """Service-facing keys; each maps to one or more Layer-2 benefit_key values."""

    VISA_SUPPORT = "visa_support"
    TEMPORARY_HOUSING = "temporary_housing"
    HOME_SEARCH = "home_search"
    SCHOOL_SEARCH = "school_search"
    HOUSEHOLD_GOODS_SHIPMENT = "household_goods_shipment"
    TAX_BRIEFING = "tax_briefing"
    TAX_FILING_SUPPORT = "tax_filing_support"
    DESTINATION_ORIENTATION = "destination_orientation"
    SPOUSE_SUPPORT = "spouse_support"
    LANGUAGE_TRAINING = "language_training"


CANONICAL_SERVICE_KEYS: FrozenSet[str] = frozenset(m.value for m in CanonicalServiceKey)

# Primary mapping: canonical service -> legacy policy_benefit_rules.benefit_key (taxonomy)
CANONICAL_SERVICE_TO_LEGACY_BENEFIT_KEY: Dict[str, str] = {
    CanonicalServiceKey.VISA_SUPPORT.value: "immigration",
    CanonicalServiceKey.TEMPORARY_HOUSING.value: "temporary_housing",
    CanonicalServiceKey.HOME_SEARCH.value: "relocation_services",
    CanonicalServiceKey.SCHOOL_SEARCH.value: "schooling",
    CanonicalServiceKey.HOUSEHOLD_GOODS_SHIPMENT.value: "shipment",
    CanonicalServiceKey.TAX_BRIEFING.value: "tax",
    CanonicalServiceKey.TAX_FILING_SUPPORT.value: "tax",
    CanonicalServiceKey.DESTINATION_ORIENTATION.value: "relocation_services",
    CanonicalServiceKey.SPOUSE_SUPPORT.value: "spouse_support",
    CanonicalServiceKey.LANGUAGE_TRAINING.value: "language_training",
}

# Legacy benefit_key -> best-effort canonical service (first match; tax disambiguation needs notes)
LEGACY_BENEFIT_KEY_TO_CANONICAL_SERVICE: Dict[str, str] = {
    "immigration": CanonicalServiceKey.VISA_SUPPORT.value,
    "temporary_housing": CanonicalServiceKey.TEMPORARY_HOUSING.value,
    "housing": CanonicalServiceKey.TEMPORARY_HOUSING.value,
    "relocation_services": CanonicalServiceKey.HOME_SEARCH.value,
    "schooling": CanonicalServiceKey.SCHOOL_SEARCH.value,
    "tuition": CanonicalServiceKey.SCHOOL_SEARCH.value,
    "shipment": CanonicalServiceKey.HOUSEHOLD_GOODS_SHIPMENT.value,
    "movers": CanonicalServiceKey.HOUSEHOLD_GOODS_SHIPMENT.value,
    "household_goods": CanonicalServiceKey.HOUSEHOLD_GOODS_SHIPMENT.value,
    "tax": CanonicalServiceKey.TAX_BRIEFING.value,
    "spouse_support": CanonicalServiceKey.SPOUSE_SUPPORT.value,
    "language_training": CanonicalServiceKey.LANGUAGE_TRAINING.value,
}


def canonical_service_for_legacy_benefit_key(benefit_key: str) -> Optional[str]:
    """Resolve canonical service_key from Layer-2 benefit_key, if known."""
    bk = (benefit_key or "").strip()
    if not bk:
        return None
    return LEGACY_BENEFIT_KEY_TO_CANONICAL_SERVICE.get(bk)


def legacy_benefit_key_for_canonical_service(service_key: str) -> Optional[str]:
    sk = (service_key or "").strip()
    if not sk:
        return None
    return CANONICAL_SERVICE_TO_LEGACY_BENEFIT_KEY.get(sk)


# category per canonical service (for defaults when building rules)
CANONICAL_SERVICE_TO_CATEGORY: Dict[str, EntitlementCategory] = {
    CanonicalServiceKey.VISA_SUPPORT.value: EntitlementCategory.IMMIGRATION,
    CanonicalServiceKey.TEMPORARY_HOUSING.value: EntitlementCategory.HOUSING,
    CanonicalServiceKey.HOME_SEARCH.value: EntitlementCategory.HOUSING,
    CanonicalServiceKey.SCHOOL_SEARCH.value: EntitlementCategory.EDUCATION,
    CanonicalServiceKey.HOUSEHOLD_GOODS_SHIPMENT.value: EntitlementCategory.RELOCATION_LOGISTICS,
    CanonicalServiceKey.TAX_BRIEFING.value: EntitlementCategory.TAX,
    CanonicalServiceKey.TAX_FILING_SUPPORT.value: EntitlementCategory.TAX,
    CanonicalServiceKey.DESTINATION_ORIENTATION.value: EntitlementCategory.INTEGRATION,
    CanonicalServiceKey.SPOUSE_SUPPORT.value: EntitlementCategory.FAMILY,
    CanonicalServiceKey.LANGUAGE_TRAINING.value: EntitlementCategory.INTEGRATION,
}


# ---------------------------------------------------------------------------
# Coverage, strength, readiness, publishability
# ---------------------------------------------------------------------------


class CoverageStatus(str, Enum):
    INCLUDED = "included"
    EXCLUDED = "excluded"
    CONDITIONAL = "conditional"
    UNKNOWN = "unknown"


COVERAGE_STATUS_VALUES: FrozenSet[str] = frozenset(m.value for m in CoverageStatus)


class RuleStrength(str, Enum):
    """
    How far the rule may progress in product surfaces.

    - draft_only: HR/draft JSON only; not shown to employees as entitlement.
    - informational: safe to show as narrative / “covered in principle” without numeric comparison.
    - comparison_ready: structured enough for envelope / cap comparison (may still need publish).
    - publish_ready: satisfies current publish gate when persisted as Layer 2.
    """

    DRAFT_ONLY = "draft_only"
    INFORMATIONAL = "informational"
    COMPARISON_READY = "comparison_ready"
    PUBLISH_READY = "publish_ready"


RULE_STRENGTH_VALUES: FrozenSet[str] = frozenset(m.value for m in RuleStrength)


class ComparisonReadiness(str, Enum):
    """Alignment with policy_processing_readiness comparison slice."""

    NOT_READY = "not_ready"
    PARTIAL = "partial"
    READY = "ready"


COMPARISON_READINESS_VALUES: FrozenSet[str] = frozenset(m.value for m in ComparisonReadiness)


class PublishabilityState(str, Enum):
    """
    Publish posture for this rule (distinct from version-level publishable flag).

    - draft_only: not materialized as Layer-2 publish rows (or only in draft_rule_candidates).
    - eligible_under_gate: Layer-2 row would pass current publish gate if version is published.
    - blocked: explicit gate or policy reason (e.g. missing provenance) — use with notes.
    - published_employee_visible: on a published policy_version and employee-visible.
    """

    DRAFT_ONLY = "draft_only"
    ELIGIBLE_UNDER_GATE = "eligible_under_gate"
    BLOCKED = "blocked"
    PUBLISHED_EMPLOYEE_VISIBLE = "published_employee_visible"


PUBLISHABILITY_VALUES: FrozenSet[str] = frozenset(m.value for m in PublishabilityState)


# ---------------------------------------------------------------------------
# Sub-structures (JSON-serializable)
# ---------------------------------------------------------------------------


class ApplicabilityFragment(TypedDict, total=False):
    assignment_types: List[str]
    family_status_terms: List[str]
    role_hints: List[str]
    duration_months_min: Optional[int]
    raw_fragments: List[str]


class LimitModel(TypedDict, total=False):
    """Structured limits; any subset may be present for partial rules."""

    amount_value: Optional[float]
    amount_unit: Optional[str]
    currency: Optional[str]
    frequency: Optional[str]
    percent_of_salary: Optional[float]
    unit_quantity: Optional[float]
    unit_label: Optional[str]
    unstructured: Optional[str]


class EmployeeVisibleValue(TypedDict, total=False):
    """What employees may see for informational or published rules (no HR-only fields)."""

    label: Optional[str]
    summary_text: Optional[str]
    numeric_max: Optional[float]
    numeric_standard: Optional[float]
    currency: Optional[str]
    unit: Optional[str]
    frequency: Optional[str]


class CanonicalEntitlementRule(TypedDict, total=False):
    """
    One canonical entitlement rule (draft candidate, Layer-2 projection, or merged HR view).

    Identifiers
    -----------
    id: Optional stable id (e.g. UUID) when persisted in a store; omitted for pure draft fragments.
    service_key: CanonicalServiceKey value.
    category: EntitlementCategory value.

    Semantics
    ---------
    coverage_status: included | excluded | conditional | unknown
    rule_strength: draft_only | informational | comparison_ready | publish_ready
    applicability: structured applicability fragments
    limit: numeric/text limit model (may be empty for informational-only)
    approval_required: whether approval is required to use the benefit
    employee_visible_value: derived employee-safe display payload
    notes: HR-only or internal notes (not shown to employees by default)
    source_excerpt: text span from policy document
    confidence: extractor/normalizer confidence [0,1]
    publishability: PublishabilityState
    comparison_readiness: ComparisonReadiness

    Traceability
    ------------
    layer2_benefit_rule_id, layer2_exclusion_id: when backed by Layer 2
    source_clause_id, policy_document_id, policy_version_id: lineage
    """

    id: str
    service_key: str
    category: str

    coverage_status: str
    rule_strength: str

    applicability: ApplicabilityFragment
    limit: LimitModel
    approval_required: bool

    employee_visible_value: EmployeeVisibleValue
    notes: str
    source_excerpt: str
    confidence: float

    publishability: str
    comparison_readiness: str

    layer2_benefit_rule_id: str
    layer2_exclusion_id: str
    source_clause_id: str
    policy_document_id: str
    policy_version_id: str


# JSON Schema shape (draft-07 compatible dict) for OpenAPI / validators
CANONICAL_ENTITLEMENT_RULE_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CanonicalEntitlementRule",
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "id": {"type": "string"},
        "service_key": {"type": "string", "enum": sorted(CANONICAL_SERVICE_KEYS)},
        "category": {"type": "string", "enum": sorted(ENTITLEMENT_CATEGORIES)},
        "coverage_status": {"type": "string", "enum": sorted(COVERAGE_STATUS_VALUES)},
        "rule_strength": {"type": "string", "enum": sorted(RULE_STRENGTH_VALUES)},
        "applicability": {"type": "object"},
        "limit": {"type": "object"},
        "approval_required": {"type": "boolean"},
        "employee_visible_value": {"type": "object"},
        "notes": {"type": "string"},
        "source_excerpt": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "publishability": {"type": "string", "enum": sorted(PUBLISHABILITY_VALUES)},
        "comparison_readiness": {"type": "string", "enum": sorted(COMPARISON_READINESS_VALUES)},
        "layer2_benefit_rule_id": {"type": "string"},
        "layer2_exclusion_id": {"type": "string"},
        "source_clause_id": {"type": "string"},
        "policy_document_id": {"type": "string"},
        "policy_version_id": {"type": "string"},
    },
    "required": ["service_key", "category", "coverage_status", "rule_strength"],
}


def infer_rule_strength(
    *,
    is_draft_candidate_only: bool,
    has_numeric_or_structured_limit: bool,
    passes_publish_gate_signals: bool,
    passes_comparison_signals: bool,
) -> str:
    """
    Heuristic mapping from pipeline signals to RuleStrength (MVP).

    Product logic may override per company (HR notes / flags).
    """
    if is_draft_candidate_only and not passes_publish_gate_signals:
        return RuleStrength.DRAFT_ONLY.value
    if passes_comparison_signals and passes_publish_gate_signals:
        return RuleStrength.PUBLISH_READY.value
    if passes_comparison_signals:
        return RuleStrength.COMPARISON_READY.value
    if has_numeric_or_structured_limit or passes_publish_gate_signals:
        return RuleStrength.INFORMATIONAL.value
    return RuleStrength.DRAFT_ONLY.value


def infer_comparison_readiness_from_flags(
    *,
    required_service_keys_satisfied: bool,
    has_decision_signal_on_required: bool,
) -> str:
    """Map coarse booleans to ComparisonReadiness (aligns with comparison_readiness slice)."""
    if required_service_keys_satisfied and has_decision_signal_on_required:
        return ComparisonReadiness.READY.value
    if required_service_keys_satisfied:
        return ComparisonReadiness.PARTIAL.value
    return ComparisonReadiness.NOT_READY.value


def merge_publishability(
    *,
    has_layer2_row: bool,
    version_published: bool,
    gate_blocked: bool,
) -> str:
    """Derive PublishabilityState from version/publish gate context."""
    if version_published and has_layer2_row and not gate_blocked:
        return PublishabilityState.PUBLISHED_EMPLOYEE_VISIBLE.value
    if gate_blocked:
        return PublishabilityState.BLOCKED.value
    if has_layer2_row:
        return PublishabilityState.ELIGIBLE_UNDER_GATE.value
    return PublishabilityState.DRAFT_ONLY.value


__all__ = [
    "EntitlementCategory",
    "ENTITLEMENT_CATEGORIES",
    "CanonicalServiceKey",
    "CANONICAL_SERVICE_KEYS",
    "CANONICAL_SERVICE_TO_LEGACY_BENEFIT_KEY",
    "LEGACY_BENEFIT_KEY_TO_CANONICAL_SERVICE",
    "CANONICAL_SERVICE_TO_CATEGORY",
    "canonical_service_for_legacy_benefit_key",
    "legacy_benefit_key_for_canonical_service",
    "CoverageStatus",
    "COVERAGE_STATUS_VALUES",
    "RuleStrength",
    "RULE_STRENGTH_VALUES",
    "ComparisonReadiness",
    "COMPARISON_READINESS_VALUES",
    "PublishabilityState",
    "PUBLISHABILITY_VALUES",
    "ApplicabilityFragment",
    "LimitModel",
    "EmployeeVisibleValue",
    "CanonicalEntitlementRule",
    "CANONICAL_ENTITLEMENT_RULE_JSON_SCHEMA",
    "infer_rule_strength",
    "infer_comparison_readiness_from_flags",
    "merge_publishability",
]
