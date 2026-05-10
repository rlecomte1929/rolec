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

    return required_fields, expanded, flags


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
