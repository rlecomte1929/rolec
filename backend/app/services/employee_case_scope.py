"""Ownership checks for employee-scoped case IDs (AIQ-2358)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def effective_relocation_case_id(assignment: Dict[str, Any]) -> str:
    """relocation_cases.id for this assignment (canonical wins over legacy case_id)."""
    cc = (assignment.get("canonical_case_id") or "").strip()
    if cc:
        return cc
    return (assignment.get("case_id") or "").strip()


def _owned_ids(assignment: Dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in ("id", "assignment_id", "case_id", "canonical_case_id"):
        val = (assignment.get(key) or "").strip()
        if val:
            ids.add(val)
    eff = effective_relocation_case_id(assignment)
    if eff:
        ids.add(eff)
    return ids


def resolve_employee_case_id(
    linked: List[Dict[str, Any]],
    case_id_override: Optional[str] = None,
) -> Optional[str]:
    """
    Pick a relocation case_id the employee owns.

    An explicit override is accepted only if it matches a linked assignment.
    Otherwise use the most recently updated linked assignment. Empty linked list
    always returns None — never honor a UUID the caller does not own.
    """
    if not linked:
        return None

    if case_id_override and case_id_override.strip():
        ov = case_id_override.strip()
        for assignment in linked:
            if ov in _owned_ids(assignment):
                return effective_relocation_case_id(assignment) or ov
        return None

    primary = max(linked, key=lambda a: (a.get("updated_at") or a.get("created_at") or ""))
    return effective_relocation_case_id(primary) or None
