"""
default_policy_template_snapshot.py — the platform-default policy template, as code.

TPL-3 / AIQ-686-adjacent retirement of the ``default_policy_templates`` table: the
table only ever held ONE seeded row (the platform default). That seed lived in
``database._seed_default_policy_template_sqlite``; this module is its canonical home
now that the table is being dropped, so the fallback/admin/import callers read it
from code (via PolicyTemplateService) instead of a DB table. Byte-for-byte the same
snapshot the table carried, so behaviour is unchanged.
"""
from __future__ import annotations

import copy
from typing import Any, Dict

PLATFORM_DEFAULT_TEMPLATE_ID = "platform-default-v2.1"

# The exact snapshot the single default_policy_templates row carried (originally
# seeded by database._seed_default_policy_template_sqlite).
_SNAPSHOT_JSON: Dict[str, Any] = {
    "policyVersion": "v2.1",
    "effectiveDate": "2024-10-01",
    "jurisdictionNotes": "Base policy for global assignments. Local counsel required for exceptions.",
    "caps": {
        "housing": {"amount": 5000, "currency": "USD", "durationMonths": 12},
        "movers": {"amount": 10000, "currency": "USD"},
        "schools": {"amount": 20000, "currency": "USD"},
        "immigration": {"amount": 4000, "currency": "USD"},
    },
    "approvalRules": {"nearLimit": "Manager", "overLimit": "HR"},
    "exceptionWorkflow": {
        "states": ["PENDING", "APPROVED", "REJECTED"],
        "requiredFields": ["category", "reason", "amount"],
    },
    "requiredEvidence": {
        "housing": ["Lease estimate", "Budget approval"],
        "movers": ["Vendor quote", "Inventory list"],
        "schools": ["School invoice", "Enrollment confirmation"],
        "immigration": ["Legal engagement letter", "Filing receipt"],
    },
    "leadTimeRules": {"minDays": 30},
    "riskThresholds": {"low": 80, "moderate": 60},
    "documentRequirements": {
        "base": ["Passport scans", "Employment letter"],
        "married": ["Marriage certificate"],
        "children": ["Birth certificates"],
        "spouseWork": ["Spouse resume"],
    },
    "approvalThresholds": {
        "housing": {"jobLevelCapOverrides": {"L1": 5000, "L2": 7000, "L3": 10000}},
        "movers": {"storageWeeksIncluded": 4},
    },
    "benefit_rules": [
        {"benefit_key": "housing", "benefit_category": "housing", "calc_type": "unit_cap", "amount_value": 5000, "amount_unit": "month", "currency": "USD"},
        {"benefit_key": "movers", "benefit_category": "movers", "calc_type": "flat_amount", "amount_value": 10000, "currency": "USD"},
        {"benefit_key": "schools", "benefit_category": "schools", "calc_type": "flat_amount", "amount_value": 20000, "currency": "USD"},
        {"benefit_key": "immigration", "benefit_category": "immigration", "calc_type": "flat_amount", "amount_value": 4000, "currency": "USD"},
    ],
}

_RECORD: Dict[str, Any] = {
    "id": PLATFORM_DEFAULT_TEMPLATE_ID,
    "template_name": "Platform default relocation policy",
    "version": "v2.1",
    "status": "active",
    "is_default_template": True,
    "snapshot_json": _SNAPSHOT_JSON,
    "created_at": "2024-10-01T00:00:00",
    "updated_at": "2024-10-01T00:00:00",
}


def get_platform_default_template() -> Dict[str, Any]:
    """The full default-template record (id, metadata, parsed snapshot_json).

    Deep-copied so callers can mutate freely without corrupting the constant.
    """
    return copy.deepcopy(_RECORD)
