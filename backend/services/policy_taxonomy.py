"""
Canonical benefit taxonomy for ReloPass policy normalization.
Single source of truth for benefit keys, categories, and keyword mapping.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Required policy themes for normalized output grouping (HR policy pipeline).
# All benefit_category values are normalized to one of these for consistent UI grouping.
POLICY_THEMES: tuple = (
    "immigration",
    "travel",
    "temporary_housing",
    "household_goods",
    "schooling",
    "spouse_support",
    "family_support",
    "banking",
    "tax",
    "allowances",
    "medical",
    "home_leave",
    "repatriation",
    "compliance",
    "documentation",
    "misc",
)
# Map taxonomy group or benefit_key -> POLICY_THEME
THEME_FROM_GROUP: Dict[str, str] = {
    "immigration": "immigration",
    "tax": "tax",
    "housing": "temporary_housing",
    "relocation": "household_goods",
    "education": "schooling",
    "travel": "travel",
    "family": "family_support",
    "integration": "documentation",
    "setup": "banking",
    "health": "medical",
    "compensation": "allowances",
}
THEME_FROM_BENEFIT_KEY: Dict[str, str] = {
    "spouse_support": "spouse_support",
    "home_leave": "home_leave",
    "banking_setup": "banking",
    "settling_in_allowance": "allowances",
    "mobility_premium": "allowances",
    "location_allowance": "allowances",
    "cola": "allowances",
    "remote_premium": "allowances",
}

# Canonical benefit keys and metadata
# Each entry: canonical_key -> { group, default_calc_type, keywords }
BENEFIT_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "immigration": {
        "group": "immigration",
        "default_calc_type": "reimbursement",
        "keywords": ["visa", "immigration", "work permit", "residence permit"],
    },
    "tax": {
        "group": "tax",
        "default_calc_type": "other",
        "keywords": ["tax equalization", "hypothetical tax", "tax protection", "tax assistance"],
    },
    "housing": {
        "group": "housing",
        "default_calc_type": "flat_amount",
        "keywords": ["housing", "accommodation", "rental", "rent"],
    },
    "temporary_housing": {
        "group": "housing",
        "default_calc_type": "unit_cap",
        "keywords": ["temporary housing", "temporary accommodation", "interim housing"],
    },
    "movers": {
        "group": "relocation",
        "default_calc_type": "flat_amount",
        "keywords": ["movers", "moving", "moving services"],
    },
    "shipment": {
        "group": "relocation",
        "default_calc_type": "flat_amount",
        "keywords": ["shipment", "household goods", "freight", "shipping"],
    },
    "storage": {
        "group": "relocation",
        "default_calc_type": "flat_amount",
        "keywords": ["storage", "temporary storage"],
    },
    "schooling": {
        "group": "education",
        "default_calc_type": "reimbursement",
        "keywords": ["school", "schooling", "education", "tuition", "international school"],
    },
    "transport": {
        "group": "travel",
        "default_calc_type": "reimbursement",
        "keywords": ["transport", "travel", "flight", "airfare", "relocation travel"],
    },
    "home_leave": {
        "group": "travel",
        "default_calc_type": "unit_cap",
        "keywords": ["home leave", "home flight", "home trip"],
    },
    "spouse_support": {
        "group": "family",
        "default_calc_type": "flat_amount",
        "keywords": ["spousal support", "spouse support", "partner support"],
    },
    "language_training": {
        "group": "integration",
        "default_calc_type": "flat_amount",
        "keywords": ["language training", "language course", "cultural training"],
    },
    "relocation_services": {
        "group": "relocation",
        "default_calc_type": "reimbursement",
        "keywords": ["relocation services", "move management", "relocation support"],
    },
    "banking_setup": {
        "group": "setup",
        "default_calc_type": "reimbursement",
        "keywords": ["banking", "bank account", "bank transfer"],
    },
    "medical": {
        "group": "health",
        "default_calc_type": "reimbursement",
        "keywords": ["medical", "health", "healthcare"],
    },
    "insurance": {
        "group": "health",
        "default_calc_type": "other",
        "keywords": ["insurance", "coverage"],
    },
    "pension": {
        "group": "compensation",
        "default_calc_type": "other",
        "keywords": ["pension", "retirement"],
    },
    "settling_in_allowance": {
        "group": "relocation",
        "default_calc_type": "flat_amount",
        "keywords": ["settling-in", "settling in", "settling in allowance"],
    },
    "mobility_premium": {
        "group": "compensation",
        "default_calc_type": "percent_salary",
        "keywords": ["mobility premium", "expatriate premium", "expat premium"],
    },
    "location_allowance": {
        "group": "compensation",
        "default_calc_type": "flat_amount",
        "keywords": ["location allowance", "location premium"],
    },
    "cola": {
        "group": "compensation",
        "default_calc_type": "percent_salary",
        "keywords": ["cola", "cost of living", "cost-of-living adjustment"],
    },
    "remote_premium": {
        "group": "compensation",
        "default_calc_type": "percent_salary",
        "keywords": ["remote premium", "hardship allowance", "hardship premium"],
    },
    # Aliases / legacy mappings
    "household_goods": {
        "group": "relocation",
        "default_calc_type": "flat_amount",
        "keywords": ["household goods", "hhg"],
        "maps_to": "shipment",
    },
    "tuition": {
        "group": "education",
        "default_calc_type": "reimbursement",
        "keywords": ["tuition", "school fees"],
        "maps_to": "schooling",
    },
    "scouting_trip": {
        "group": "travel",
        "default_calc_type": "unit_cap",
        "keywords": ["scouting trip", "pre-assignment visit", "look-see"],
    },
}

# Valid calc types
CALC_TYPES = frozenset([
    "percent_salary", "flat_amount", "unit_cap", "reimbursement",
    "difference_only", "per_diem", "other",
])

# Valid condition types
CONDITION_TYPES = frozenset([
    "assignment_type", "family_status", "duration_threshold",
    "accompanied_family", "localization_exclusion", "remote_location",
    "school_age_threshold", "other",
])

# Assignment type normalization
ASSIGNMENT_TYPE_MAP = {
    "long_term": "LTA",
    "lta": "LTA",
    "long-term": "LTA",
    "short_term": "STA",
    "sta": "STA",
    "short-term": "STA",
    "permanent": "PERMANENT",
    "commuter": "COMMUTER",
    "international": "LTA",
}

# Family status normalization
FAMILY_STATUS_MAP = {
    "single": "single",
    "married": "married",
    "spouse": "accompanied",
    "dependents": "with_children",
    "accompanying": "accompanied",
    "family": "accompanied",
    "unaccompanied": "unaccompanied",
}


def resolve_benefit_key(candidate: Optional[str], section_label: Optional[str], raw_text: str) -> Optional[str]:
    """
    Resolve a candidate benefit key or infer from context to a canonical key.
    Returns canonical key or None.
    """
    text_lower = raw_text.lower()
    if section_label:
        section_lower = section_label.lower()

    # Direct candidate mapping
    if candidate:
        cand = candidate.lower().replace("-", "_")
        if cand in BENEFIT_TAXONOMY:
            return cand
        # Check maps_to
        for key, meta in BENEFIT_TAXONOMY.items():
            if meta.get("maps_to") and cand == key:
                return meta["maps_to"]

    # Infer from section
    if section_label:
        for key, meta in BENEFIT_TAXONOMY.items():
            for kw in meta["keywords"]:
                if kw in section_lower:
                    return key

    # Infer from raw text
    for key, meta in BENEFIT_TAXONOMY.items():
        for kw in meta["keywords"]:
            if kw in text_lower:
                return key

    return None


def get_benefit_meta(benefit_key: str) -> Dict[str, Any]:
    """Get taxonomy metadata for a canonical benefit key."""
    key = benefit_key.lower().replace("-", "_")
    return BENEFIT_TAXONOMY.get(key, {"group": "other", "default_calc_type": "other", "keywords": []})


def resolve_theme(benefit_key: str, group: Optional[str] = None) -> str:
    """
    Resolve benefit_key and optional group to a POLICY_THEMES category.
    Used so normalized output is grouped by a stable set of themes.
    """
    key = (benefit_key or "").lower().replace("-", "_")
    if key and key in THEME_FROM_BENEFIT_KEY:
        return THEME_FROM_BENEFIT_KEY[key]
    g = (group or "").lower()
    if g in THEME_FROM_GROUP:
        return THEME_FROM_GROUP[g]
    return "misc"


def list_canonical_keys() -> List[str]:
    """List all canonical benefit keys (excluding aliases that map elsewhere)."""
    return [k for k, m in BENEFIT_TAXONOMY.items() if not m.get("maps_to")]
