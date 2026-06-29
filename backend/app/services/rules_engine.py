from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Tuple, Optional


def apply_rules(case_draft: Dict[str, Any], base_requirements: List[Dict[str, Any]]) -> Tuple[List[str], List[Dict[str, Any]], Dict[str, Any]]:
    required_fields: List[str] = []
    expanded = list(base_requirements)
    flags: Dict[str, Any] = {}

    basics = case_draft.get("relocationBasics", {})
    family = case_draft.get("familyMembers", {})
    assignment = case_draft.get("assignmentContext", {})
    profile = case_draft.get("employeeProfile", {})

    purpose = basics.get("purpose")
    has_dependents = basics.get("hasDependents")
    # AIQ-1349 Phase 2: short-term assignments (STA, typically <12 months) don't
    # trigger the long-term, family-settling requirements — a spouse rarely seeks
    # local work authorization and children aren't enrolled in a local school for
    # a brief posting. Suppress those two so STA gets a lighter requirement set.
    # (LTA/PERMANENT keep the full set.)
    case_assignment_type = str(assignment.get("assignmentType") or "").strip().upper() or None
    is_sta = case_assignment_type == "STA"

    if basics.get("targetMoveDate") and profile.get("passportExpiry"):
        try:
            target = date.fromisoformat(str(basics["targetMoveDate"]))
            expiry = date.fromisoformat(str(profile["passportExpiry"]))
            if expiry <= target:
                expanded.append(_requirement(
                    "Passport expiry must be after target move date",
                    "IDENTITY",
                    "WARN",
                    "EMPLOYEE",
                    ["employeeProfile.passportExpiry"],
                ))
        except Exception:
            pass

    if has_dependents:
        required_fields += ["familyMembers.spouse.fullName", "familyMembers.children"]
        flags["hasDependents"] = True

    spouse = (family.get("spouse") or {})
    if spouse and spouse.get("wantsToWork"):
        if is_sta:
            flags.setdefault("staWaived", []).append("Dependent work authorization rules")
        else:
            expanded.append(_requirement(
                "Dependent work authorization rules",
                "DEPENDENTS",
                "WARN",
                "HR",
                ["familyMembers.spouse"],
            ))
            flags["spouseWork"] = True

    children = family.get("children") or []
    if children:
        flags["kids"] = True
        for child in children:
            if _child_age(child.get("dateOfBirth")) in range(5, 17):
                if is_sta:
                    flags.setdefault("staWaived", []).append("School enrollment documents")
                else:
                    expanded.append(_requirement(
                        "School enrollment documents",
                        "DEPENDENTS",
                        "WARN",
                        "HR",
                        ["familyMembers.children"],
                    ))
                    flags["kidsSchoolAge"] = True
                break

    if purpose == "employment":
        required_fields += [
            "assignmentContext.employerName",
            "assignmentContext.jobTitle",
            "assignmentContext.contractStartDate",
        ]

    # AIQ-1349: data-driven applicability. A requirement may declare
    # appliesToAssignmentTypes (a list, e.g. ["LTA","PERMANENT"]); drop it for a
    # case whose assignment_type isn't listed. None/empty ⇒ applies to all. Only
    # filters when the case has a known assignment_type (legacy cases keep all).
    if case_assignment_type:
        dropped = [r for r in expanded if not _applies_to_assignment_type(r, case_assignment_type)]
        if dropped:
            expanded = [r for r in expanded if _applies_to_assignment_type(r, case_assignment_type)]
            flags.setdefault("staWaived", []).extend(
                r.get("title") for r in dropped if r.get("title")
            )

    return required_fields, expanded, flags


def _applies_to_assignment_type(requirement: Dict[str, Any], case_assignment_type: str) -> bool:
    """True when the requirement applies to the case's assignment type. A
    requirement with no ``appliesToAssignmentTypes`` (None/empty) applies to all."""
    allowed = requirement.get("appliesToAssignmentTypes")
    if not allowed:
        return True
    norm = {str(a).strip().upper() for a in allowed if str(a).strip()}
    return (not norm) or (case_assignment_type in norm)


def _child_age(date_str: Optional[str]) -> int:
    if not date_str:
        return 0
    try:
        dob = date.fromisoformat(str(date_str))
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return 0


def _requirement(title: str, pillar: str, severity: str, owner: str, required_fields: List[str]) -> Dict[str, Any]:
    return {
        "title": title,
        "pillar": pillar,
        "description": "System-generated requirement based on case context.",
        "severity": severity,
        "owner": owner,
        "requiredFields": required_fields,
    }
