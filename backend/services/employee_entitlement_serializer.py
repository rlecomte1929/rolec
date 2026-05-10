"""
Stable JSON shape for GET employee assignment entitlements.
"""
from __future__ import annotations

from typing import Any, Dict

EMPLOYEE_ENTITLEMENT_SCHEMA_VERSION = "1.0"


def serialize_employee_entitlement_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap read-model dict with schema version for clients."""
    return {
        "schema_version": EMPLOYEE_ENTITLEMENT_SCHEMA_VERSION,
        "policy_status": payload.get("policy_status"),
        "policy_source": payload.get("policy_source"),
        "publish_readiness": payload.get("publish_readiness"),
        "comparison_readiness": payload.get("comparison_readiness"),
        "explanation": payload.get("explanation"),
        "entitlements": payload.get("entitlements") or [],
        "assignment_id": payload.get("assignment_id"),
        "company_id": payload.get("company_id"),
        "policy_id": payload.get("policy_id"),
        "version_id": payload.get("version_id"),
    }
