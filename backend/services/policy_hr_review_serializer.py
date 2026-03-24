"""
JSON-safe serialization for HR policy review API responses.
"""
from __future__ import annotations

from typing import Any, Dict

# Bumped when HR-facing review shape changes (e.g. grouped_review / template domains).
HR_POLICY_REVIEW_SCHEMA_VERSION = 2


def serialize_hr_policy_review_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Attach API schema version; payload is already JSON-serializable dicts.

    Ensures ``grouped_review`` is present for forward-compatible clients (empty structure
    if the service did not attach it).
    """
    out = dict(payload)
    out["schema_version"] = HR_POLICY_REVIEW_SCHEMA_VERSION
    if "grouped_review" not in out or out["grouped_review"] is None:
        out["grouped_review"] = {
            "template_domains": {},
            "domain_order": [],
            "import_summary": {},
            "duplicate_merge_summary": {},
            "counts": {},
            "items_needing_review": {"grouped_rows": 0, "template_fields": 0},
            "empty_template_slots_by_domain": {},
        }
    return out
