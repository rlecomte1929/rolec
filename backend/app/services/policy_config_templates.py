"""
DEPRECATED (N12/AIQ-852): one of four legacy template systems now unified by
``policy_template_service.PolicyTemplateService`` (``POLICY_TEMPLATES`` below was
ported into the versioned registry). Left in place until a follow-up cleanup task
retires it after validation — do not extend; add new template data to the unified
service instead.

Starter-baseline templates for the Compensation & Allowance matrix.

Product decision (2026-04-22): HR should be able to start a new draft
from an opinionated baseline — Conservative / Standard / Premium —
with level-tiered caps already pre-filled (Entry Level / Manager /
Director / VP / C-suite) so the first draft is a useful scaffold, not
a blank matrix.

How this works:
  - Each template declares a list of "template rows". A row is either:
      * FLAT — one output row, applies to all levels (empty
        employee_levels array). Used for service-category caps like
        shipment or temporary living where level-tiering isn't
        meaningful day one.
      * TIERED — expands into five output rows, one per employee
        level, with a level-specific amount. Used for cash allowances
        where the level really does change the number (relocation
        allowance, spouse assistance, etc.).
  - The set of benefit_keys here is intentionally a curated subset of
    _CANONICAL_KEYS in policy_config_matrix_service.py — the 15-ish
    lines HR actually tunes. Missing keys stay unset in the draft
    (HR adds them later via the row drawer if needed).
  - Numbers are reasonable-default placeholders, not legal advice.
    Product can tune them centrally without touching code that applies
    them.

Keeping templates as Python data (not JSON on disk) so they ship with
the image, version-control cleanly, and can be exercised by unit tests
without filesystem IO.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .policy_config_targeting import EMPLOYEE_LEVELS

# --- Types used below -------------------------------------------------------

TieredAmountMap = Dict[str, float]  # level slug -> amount
FlatRow = Dict[str, Any]
TieredRow = Dict[str, Any]


def _tiered_amounts(
    *,
    entry: float,
    manager: float,
    director: float,
    vp: float,
    c_suite: float,
) -> TieredAmountMap:
    """Named-argument constructor so the template declarations read clearly.
    Missing a level would silently default to 0 otherwise; force callers to
    provide all five."""
    return {
        "entry": entry,
        "manager": manager,
        "director": director,
        "vp": vp,
        "c_suite": c_suite,
    }


# --- Three templates --------------------------------------------------------
#
# Row schema
#   {
#     "benefit_key": str,        # must match a row registered in
#                                # policy_config_matrix_service._CANONICAL_KEYS
#     "category": str,           # matrix category value
#     "covered": bool,           # whether the row is in-policy
#     "value_type": str,         # "currency" | "percentage" | "none"
#     "currency_code": str?,     # required when value_type="currency"
#     "unit_frequency": str,     # "one_time" | "monthly" | "per_trip" | ...
#     "notes": str?,             # short employee-facing hint
#     # One of:
#     "amount": float            # flat row
#     "amounts_by_level": dict   # tiered row → expands into 5 rows
#     "percentage": float        # percentage flat row
#   }

_RELOCATION_ALLOWANCE_ASSIGNEE = "relocation_allowance_assignee_partner"
_RELOCATION_ALLOWANCE_DEPENDENT = "relocation_allowance_dependent"
_MOBILITY_PREMIUM = "mobility_premium"
_LOCATION_ALLOWANCE = "location_allowance"
_SPOUSE_PARTNER_ASSISTANCE = "spouse_partner_assistance"
_CHILD_EDUCATION_SUPPORT = "child_education_support"
_REPATRIATION_ALLOWANCE_ASSIGNEE = "repatriation_allowance_assignee_partner"
_REPATRIATION_ALLOWANCE_DEPENDENT = "repatriation_allowance_dependent"
_SHIPMENT_OF_GOODS = "shipment_of_goods"
_STORAGE = "storage"
_TEMPORARY_LIVING = "temporary_living"
_SETTLING_IN_SERVICES = "settling_in_services"
_LANGUAGE_TRAINING = "language_training"
_CULTURAL_TRAINING = "cultural_training"
_PRE_ASSIGNMENT_VISIT = "pre_assignment_visit"
_VISA_WORK_PERMIT = "visa_work_permit_assistance"
_MEDICAL_EXAM = "medical_exam_reimbursement"
_TAX_EQUALISATION = "tax_equalisation"
_TAX_RETURN_PREP = "tax_return_preparation"
_BANKING_ASSISTANCE = "banking_assistance"
_HOME_LEAVE_TRIPS = "home_leave_trips"

PRE_ASSIGNMENT_SUPPORT = "pre_assignment_support"
RELOCATION_ASSISTANCE = "relocation_assistance"
COMPENSATION_ALLOWANCES = "compensation_allowances"
FAMILY_SUPPORT_EDUCATION = "family_support_education"
LEAVE_REPATRIATION = "leave_repatriation"
TAX_PAYROLL = "tax_payroll"


POLICY_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "conservative": {
        "key": "conservative",
        "label": "Conservative",
        "description": (
            "Cautious defaults with lower caps — a safe starting point you can "
            "raise as your mobility program matures. Covers essentials only; "
            "non-essential items stay excluded."
        ),
        "rows": [
            # Pre-assignment
            {"benefit_key": _VISA_WORK_PERMIT, "category": PRE_ASSIGNMENT_SUPPORT,
             "covered": True, "value_type": "none", "unit_frequency": "one_time",
             "notes": "Company-supported work permit & visa processing."},
            {"benefit_key": _MEDICAL_EXAM, "category": PRE_ASSIGNMENT_SUPPORT,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time", "amount": 300,
             "notes": "Pre-departure medical exam reimbursement."},
            {"benefit_key": _PRE_ASSIGNMENT_VISIT, "category": PRE_ASSIGNMENT_SUPPORT,
             "covered": False, "value_type": "none", "unit_frequency": "one_time"},
            {"benefit_key": _CULTURAL_TRAINING, "category": PRE_ASSIGNMENT_SUPPORT,
             "covered": False, "value_type": "none", "unit_frequency": "one_time"},
            # Relocation assistance — tiered lump sum
            {"benefit_key": _RELOCATION_ALLOWANCE_ASSIGNEE, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time",
             "amounts_by_level": _tiered_amounts(
                 entry=2000, manager=3000, director=4500, vp=6000, c_suite=8000),
             "notes": "Lump-sum relocation allowance for the assignee and accompanying partner."},
            {"benefit_key": _RELOCATION_ALLOWANCE_DEPENDENT, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "per_dependent",
             "amounts_by_level": _tiered_amounts(
                 entry=500, manager=750, director=1000, vp=1250, c_suite=1500),
             "notes": "Per dependent, paid alongside the assignee allowance."},
            {"benefit_key": _SHIPMENT_OF_GOODS, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time", "amount": 8000,
             "notes": "Capped outbound shipment of household goods."},
            {"benefit_key": _STORAGE, "category": RELOCATION_ASSISTANCE,
             "covered": False, "value_type": "none", "unit_frequency": "monthly"},
            {"benefit_key": _TEMPORARY_LIVING, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "none", "unit_frequency": "one_time",
             "notes": "Up to 14 days of temporary accommodation at start of assignment."},
            {"benefit_key": _SETTLING_IN_SERVICES, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "none", "unit_frequency": "one_time",
             "notes": "Home search + basic settling-in support (no school search)."},
            # Compensation
            {"benefit_key": _MOBILITY_PREMIUM, "category": COMPENSATION_ALLOWANCES,
             "covered": False, "value_type": "none", "unit_frequency": "monthly"},
            {"benefit_key": _LOCATION_ALLOWANCE, "category": COMPENSATION_ALLOWANCES,
             "covered": False, "value_type": "none", "unit_frequency": "monthly"},
            # Family
            {"benefit_key": _SPOUSE_PARTNER_ASSISTANCE, "category": FAMILY_SUPPORT_EDUCATION,
             "covered": False, "value_type": "none", "unit_frequency": "one_time"},
            {"benefit_key": _CHILD_EDUCATION_SUPPORT, "category": FAMILY_SUPPORT_EDUCATION,
             "covered": False, "value_type": "none", "unit_frequency": "yearly"},
            # Leave & repatriation
            {"benefit_key": _HOME_LEAVE_TRIPS, "category": LEAVE_REPATRIATION,
             "covered": False, "value_type": "none", "unit_frequency": "yearly"},
            {"benefit_key": _REPATRIATION_ALLOWANCE_ASSIGNEE, "category": LEAVE_REPATRIATION,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time",
             "amounts_by_level": _tiered_amounts(
                 entry=2000, manager=3000, director=4500, vp=6000, c_suite=8000),
             "notes": "Lump-sum repatriation allowance at end of assignment."},
            # Tax & payroll
            {"benefit_key": _TAX_EQUALISATION, "category": TAX_PAYROLL,
             "covered": False, "value_type": "none", "unit_frequency": "yearly"},
            {"benefit_key": _TAX_RETURN_PREP, "category": TAX_PAYROLL,
             "covered": False, "value_type": "none", "unit_frequency": "yearly"},
            {"benefit_key": _BANKING_ASSISTANCE, "category": TAX_PAYROLL,
             "covered": False, "value_type": "none", "unit_frequency": "monthly"},
        ],
    },
    "standard": {
        "key": "standard",
        "label": "Standard",
        "description": (
            "Balanced baseline most mid-market mobility programs land on. "
            "Level-tiered cash allowances, service coverage for the usual "
            "relocation categories, tax support included."
        ),
        "rows": [
            {"benefit_key": _VISA_WORK_PERMIT, "category": PRE_ASSIGNMENT_SUPPORT,
             "covered": True, "value_type": "none", "unit_frequency": "one_time"},
            {"benefit_key": _MEDICAL_EXAM, "category": PRE_ASSIGNMENT_SUPPORT,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time", "amount": 500},
            {"benefit_key": _PRE_ASSIGNMENT_VISIT, "category": PRE_ASSIGNMENT_SUPPORT,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time", "amount": 2500,
             "notes": "Pre-assignment look-see trip for assignee and spouse/partner."},
            {"benefit_key": _CULTURAL_TRAINING, "category": PRE_ASSIGNMENT_SUPPORT,
             "covered": True, "value_type": "none", "unit_frequency": "one_time",
             "notes": "Destination-country cultural briefing."},
            {"benefit_key": _LANGUAGE_TRAINING, "category": PRE_ASSIGNMENT_SUPPORT,
             "covered": True, "value_type": "none", "unit_frequency": "one_time",
             "notes": "Up to 40 hours of host-language lessons for assignee and partner."},
            # Relocation assistance
            {"benefit_key": _RELOCATION_ALLOWANCE_ASSIGNEE, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time",
             "amounts_by_level": _tiered_amounts(
                 entry=3000, manager=5000, director=8000, vp=12000, c_suite=18000)},
            {"benefit_key": _RELOCATION_ALLOWANCE_DEPENDENT, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "per_dependent",
             "amounts_by_level": _tiered_amounts(
                 entry=1000, manager=1500, director=2000, vp=2500, c_suite=3000)},
            {"benefit_key": _SHIPMENT_OF_GOODS, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time", "amount": 20000},
            {"benefit_key": _STORAGE, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "none", "unit_frequency": "monthly",
             "notes": "Up to 6 months of storage while temporary living."},
            {"benefit_key": _TEMPORARY_LIVING, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "none", "unit_frequency": "one_time",
             "notes": "Up to 30 days at start and end of assignment."},
            {"benefit_key": _SETTLING_IN_SERVICES, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "none", "unit_frequency": "one_time",
             "notes": "Home search, school search, documentation, bank setup."},
            # Compensation & allowances
            {"benefit_key": _MOBILITY_PREMIUM, "category": COMPENSATION_ALLOWANCES,
             "covered": True, "value_type": "percentage", "percentage": 10.0,
             "unit_frequency": "monthly",
             "notes": "Percentage of base salary paid monthly for duration of assignment."},
            {"benefit_key": _LOCATION_ALLOWANCE, "category": COMPENSATION_ALLOWANCES,
             "covered": True, "value_type": "none", "unit_frequency": "monthly",
             "notes": "Location premium based on third-party hardship data."},
            # Family
            {"benefit_key": _SPOUSE_PARTNER_ASSISTANCE, "category": FAMILY_SUPPORT_EDUCATION,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time",
             "amounts_by_level": _tiered_amounts(
                 entry=3000, manager=5000, director=7500, vp=10000, c_suite=15000),
             "notes": "One-off career transition support for accompanying spouse/partner."},
            {"benefit_key": _CHILD_EDUCATION_SUPPORT, "category": FAMILY_SUPPORT_EDUCATION,
             "covered": True, "value_type": "none", "unit_frequency": "yearly",
             "notes": "Difference in tuition between home and host country schooling."},
            # Leave & repatriation
            {"benefit_key": _HOME_LEAVE_TRIPS, "category": LEAVE_REPATRIATION,
             "covered": True, "value_type": "none", "unit_frequency": "yearly",
             "notes": "One home leave round trip per 12 months, economy class."},
            {"benefit_key": _REPATRIATION_ALLOWANCE_ASSIGNEE, "category": LEAVE_REPATRIATION,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time",
             "amounts_by_level": _tiered_amounts(
                 entry=3000, manager=5000, director=8000, vp=12000, c_suite=18000)},
            {"benefit_key": _REPATRIATION_ALLOWANCE_DEPENDENT, "category": LEAVE_REPATRIATION,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "per_dependent",
             "amounts_by_level": _tiered_amounts(
                 entry=1000, manager=1500, director=2000, vp=2500, c_suite=3000)},
            # Tax
            {"benefit_key": _TAX_EQUALISATION, "category": TAX_PAYROLL,
             "covered": True, "value_type": "none", "unit_frequency": "yearly",
             "notes": "Tax-equalized compensation approach with gross-up."},
            {"benefit_key": _TAX_RETURN_PREP, "category": TAX_PAYROLL,
             "covered": True, "value_type": "none", "unit_frequency": "yearly",
             "notes": "Home + host country tax return preparation."},
            {"benefit_key": _BANKING_ASSISTANCE, "category": TAX_PAYROLL,
             "covered": True, "value_type": "none", "unit_frequency": "monthly",
             "notes": "Reimbursement for one home-to-host bank transfer per month."},
        ],
    },
    "premium": {
        "key": "premium",
        "label": "Premium",
        "description": (
            "Full-service executive-grade defaults. Higher caps across the "
            "board, richer family support, and tax equalization included. "
            "Best for international leadership moves."
        ),
        "rows": [
            {"benefit_key": _VISA_WORK_PERMIT, "category": PRE_ASSIGNMENT_SUPPORT,
             "covered": True, "value_type": "none", "unit_frequency": "one_time"},
            {"benefit_key": _MEDICAL_EXAM, "category": PRE_ASSIGNMENT_SUPPORT,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time", "amount": 1000},
            {"benefit_key": _PRE_ASSIGNMENT_VISIT, "category": PRE_ASSIGNMENT_SUPPORT,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time", "amount": 5000},
            {"benefit_key": _CULTURAL_TRAINING, "category": PRE_ASSIGNMENT_SUPPORT,
             "covered": True, "value_type": "none", "unit_frequency": "one_time"},
            {"benefit_key": _LANGUAGE_TRAINING, "category": PRE_ASSIGNMENT_SUPPORT,
             "covered": True, "value_type": "none", "unit_frequency": "one_time",
             "notes": "Up to 80 hours of language training for family members."},
            # Relocation assistance — premium caps
            {"benefit_key": _RELOCATION_ALLOWANCE_ASSIGNEE, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time",
             "amounts_by_level": _tiered_amounts(
                 entry=5000, manager=8000, director=12000, vp=18000, c_suite=25000)},
            {"benefit_key": _RELOCATION_ALLOWANCE_DEPENDENT, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "per_dependent",
             "amounts_by_level": _tiered_amounts(
                 entry=1500, manager=2000, director=3000, vp=4000, c_suite=5000)},
            {"benefit_key": _SHIPMENT_OF_GOODS, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time", "amount": 35000},
            {"benefit_key": _STORAGE, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "none", "unit_frequency": "monthly",
             "notes": "Up to 12 months of storage while temporary living."},
            {"benefit_key": _TEMPORARY_LIVING, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "none", "unit_frequency": "one_time",
             "notes": "Up to 60 days at start and end of assignment."},
            {"benefit_key": _SETTLING_IN_SERVICES, "category": RELOCATION_ASSISTANCE,
             "covered": True, "value_type": "none", "unit_frequency": "one_time"},
            # Compensation
            {"benefit_key": _MOBILITY_PREMIUM, "category": COMPENSATION_ALLOWANCES,
             "covered": True, "value_type": "percentage", "percentage": 15.0,
             "unit_frequency": "monthly"},
            {"benefit_key": _LOCATION_ALLOWANCE, "category": COMPENSATION_ALLOWANCES,
             "covered": True, "value_type": "none", "unit_frequency": "monthly"},
            # Family
            {"benefit_key": _SPOUSE_PARTNER_ASSISTANCE, "category": FAMILY_SUPPORT_EDUCATION,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time",
             "amounts_by_level": _tiered_amounts(
                 entry=5000, manager=8000, director=12000, vp=18000, c_suite=25000)},
            {"benefit_key": _CHILD_EDUCATION_SUPPORT, "category": FAMILY_SUPPORT_EDUCATION,
             "covered": True, "value_type": "none", "unit_frequency": "yearly",
             "notes": "International school tuition covered for dependent children."},
            # Leave & repatriation
            {"benefit_key": _HOME_LEAVE_TRIPS, "category": LEAVE_REPATRIATION,
             "covered": True, "value_type": "none", "unit_frequency": "yearly",
             "notes": "Two home leave round trips per 12 months for the whole family, business class for the assignee."},
            {"benefit_key": _REPATRIATION_ALLOWANCE_ASSIGNEE, "category": LEAVE_REPATRIATION,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "one_time",
             "amounts_by_level": _tiered_amounts(
                 entry=5000, manager=8000, director=12000, vp=18000, c_suite=25000)},
            {"benefit_key": _REPATRIATION_ALLOWANCE_DEPENDENT, "category": LEAVE_REPATRIATION,
             "covered": True, "value_type": "currency", "currency_code": "EUR",
             "unit_frequency": "per_dependent",
             "amounts_by_level": _tiered_amounts(
                 entry=1500, manager=2000, director=3000, vp=4000, c_suite=5000)},
            # Tax
            {"benefit_key": _TAX_EQUALISATION, "category": TAX_PAYROLL,
             "covered": True, "value_type": "none", "unit_frequency": "yearly"},
            {"benefit_key": _TAX_RETURN_PREP, "category": TAX_PAYROLL,
             "covered": True, "value_type": "none", "unit_frequency": "yearly"},
            {"benefit_key": _BANKING_ASSISTANCE, "category": TAX_PAYROLL,
             "covered": True, "value_type": "none", "unit_frequency": "monthly"},
        ],
    },
}


def list_templates() -> List[Dict[str, Any]]:
    """Metadata for the picker UI — no row data, fast to serialize."""
    return [
        {
            "key": v["key"],
            "label": v["label"],
            "description": v["description"],
        }
        for v in POLICY_TEMPLATES.values()
    ]


def get_template(key: str) -> Optional[Dict[str, Any]]:
    return POLICY_TEMPLATES.get(str(key).strip().lower())


def expand_template_rows(template_key: str) -> List[Dict[str, Any]]:
    """
    Expand a template into a list of concrete benefit rows ready to
    insert into a draft. Tiered rows become N rows (one per
    employee level). Display order follows the declaration order; the
    matrix service will re-sort by category + display_order on read.

    Raises KeyError if the template key is unknown.
    """
    tpl = get_template(template_key)
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
