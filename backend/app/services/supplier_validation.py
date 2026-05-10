"""Validation rules for Supplier Registry admin operations."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

VALID_STATUSES = ("active", "inactive", "draft")
VALID_COVERAGE_SCOPE_TYPES = ("global", "country", "city")

# Service categories from recommendation registry (must match plugins)
VALID_SERVICE_CATEGORIES = frozenset({
    "living_areas",
    "schools",
    "movers",
    "banks",
    "insurance",
    "electricity",
    "medical",
    "telecom",
    "childcare",
    "storage",
    "transport",
    "language_integration",
    "legal_admin",
    "tax_finance",
    "general",  # fallback
})


def validate_supplier_create(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate create supplier payload."""
    if not isinstance(data, dict):
        return False, "Payload must be an object"
    name = (data.get("name") or "").strip()
    if not name:
        return False, "name is required"
    status = (data.get("status") or "active").lower()
    if status not in VALID_STATUSES:
        return False, f"status must be one of {VALID_STATUSES}"
    caps = data.get("capabilities", [])
    if isinstance(caps, list):
        for i, c in enumerate(caps):
            ok, err = validate_capability(c, exclude_id=True)
            if not ok:
                return False, f"capabilities[{i}]: {err}"
    return True, None


def validate_supplier_update(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate update supplier payload (partial)."""
    if not isinstance(data, dict):
        return False, "Payload must be an object"
    if "name" in data and not str(data.get("name") or "").strip():
        return False, "name cannot be empty"
    if "status" in data:
        s = (data["status"] or "").lower()
        if s not in VALID_STATUSES:
            return False, f"status must be one of {VALID_STATUSES}"
    return True, None


def validate_capability(
    data: Dict[str, Any],
    *,
    exclude_id: bool = False,
) -> Tuple[bool, Optional[str]]:
    """Validate capability payload."""
    if not isinstance(data, dict):
        return False, "Capability must be an object"
    svc = (data.get("service_category") or "general").lower().replace(" ", "_")
    if svc not in VALID_SERVICE_CATEGORIES:
        return False, f"service_category must be one of {sorted(VALID_SERVICE_CATEGORIES)}"
    scope = (data.get("coverage_scope_type") or "country").lower()
    if scope not in VALID_COVERAGE_SCOPE_TYPES:
        return False, f"coverage_scope_type must be one of {VALID_COVERAGE_SCOPE_TYPES}"
    if scope == "country":
        cc = (data.get("country_code") or "").strip().upper()
        if not cc or len(cc) < 2:
            return False, "country_code (2-letter) required when coverage_scope_type is country"
    if scope == "city":
        if not (data.get("country_code") or "").strip():
            return False, "country_code required when coverage_scope_type is city"
        if not (data.get("city_name") or "").strip():
            return False, "city_name required when coverage_scope_type is city"
    if data.get("min_budget") is not None:
        try:
            v = float(data["min_budget"])
            if v < 0:
                return False, "min_budget must be >= 0"
        except (TypeError, ValueError):
            return False, "min_budget must be a number"
    if data.get("max_budget") is not None:
        try:
            v = float(data["max_budget"])
            if v < 0:
                return False, "max_budget must be >= 0"
        except (TypeError, ValueError):
            return False, "max_budget must be a number"
    min_b = data.get("min_budget")
    max_b = data.get("max_budget")
    if min_b is not None and max_b is not None:
        try:
            if float(min_b) > float(max_b):
                return False, "min_budget cannot exceed max_budget"
        except (TypeError, ValueError):
            pass
    return True, None


def capability_signature(
    service_category: str,
    coverage_scope_type: str,
    country_code: Optional[str],
    city_name: Optional[str],
) -> Tuple[str, str, str, str]:
    """Normalized tuple for duplicate detection."""
    return (
        (service_category or "general").lower(),
        (coverage_scope_type or "country").lower(),
        (country_code or "").strip().upper()[:2] or "",
        (city_name or "").strip(),
    )


def check_duplicate_capability(
    existing_caps: List[Dict[str, Any]],
    new_cap: Dict[str, Any],
    exclude_cap_id: Optional[str] = None,
) -> bool:
    """Return True if new_cap would be a duplicate of an existing capability."""
    sig = capability_signature(
        new_cap.get("service_category"),
        new_cap.get("coverage_scope_type"),
        new_cap.get("country_code"),
        new_cap.get("city_name"),
    )
    for c in existing_caps:
        if exclude_cap_id and str(c.get("id")) == str(exclude_cap_id):
            continue
        existing_sig = capability_signature(
            c.get("service_category"),
            c.get("coverage_scope_type"),
            c.get("country_code"),
            c.get("city_name"),
        )
        if existing_sig == sig:
            return True
    return False


def get_valid_service_categories() -> List[str]:
    """Return sorted list of valid service categories for API."""
    return sorted(VALID_SERVICE_CATEGORIES - {"general"})


def validate_active_supplier_requirements(supplier: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """For status=active, ensure required fields. Name is always required."""
    if supplier.get("status") != "active":
        return True, None
    if not (supplier.get("name") or "").strip():
        return False, "name is required for active suppliers"
    return True, None
