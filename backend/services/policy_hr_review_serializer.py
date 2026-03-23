"""
JSON-safe serialization for HR policy review API responses.
"""
from __future__ import annotations

from typing import Any, Dict

HR_POLICY_REVIEW_SCHEMA_VERSION = 1


def serialize_hr_policy_review_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach API schema version; payload is already JSON-serializable dicts."""
    out = dict(payload)
    out["schema_version"] = HR_POLICY_REVIEW_SCHEMA_VERSION
    return out
