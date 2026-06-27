"""Server-authoritative port of the wizard's intake-draft converter (AIQ-1311).

The v2 "Pathway" wizard autosaves a **flat snake_case** draft to
``case_assignments.intake_draft``; the submit guard
(:mod:`backend.intake_completeness`) and the relocation-profile promotion both
read the canonical **camelCase nested** ``CaseDraftDTO`` shape. This function is
the bridge, so the backend can validate/promote straight from the reliable
assignment autosave instead of depending on the frontend having patched the
right ``wizard_cases`` row.

It is a 1:1 port of
``frontend/src/features/platform-v2/intake/intakeToCaseDraft.ts`` — keep the two
in lockstep. Pure (no app/DB deps) so it unit-tests in isolation, like
:mod:`backend.intake_completeness`.

Empty/blank fields are dropped (left absent) — never emitted as empty strings —
so the backend deep-merge keeps any existing value rather than overwriting good
data with blanks (mirrors the TS converter's ``|| undefined``).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _s(value: Any) -> Optional[str]:
    """A string field as ``value or None`` — TS ``x || undefined``. Blank → None."""
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    return text or None


def _drop_none(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def intake_draft_to_case_draft(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Map the wizard's snake_case ``IntakeData`` onto the canonical
    camelCase-nested ``CaseDraftDTO`` the case record, HR views, and the
    roadmap all read."""
    data = data or {}
    members: List[Dict[str, Any]] = data.get("members") or []
    partner = next((m for m in members if m.get("kind") == "partner"), None)
    children = [m for m in members if m.get("kind") == "child"]
    has_dependents = any(m.get("kind") in ("partner", "child") for m in members)

    relocation_basics = _drop_none(
        {
            "originCountry": _s(data.get("origin_country")),
            "originCity": _s(data.get("origin_city")),
            "destCountry": _s(data.get("dest_country")),
            "destCity": _s(data.get("dest_city")),
            "purpose": _s(data.get("purpose")),
            "targetMoveDate": _s(data.get("target_date")),
        }
    )
    # Always present (a valid boolean, not a blank-droppable string).
    relocation_basics["hasDependents"] = has_dependents

    employee_profile = _drop_none(
        {
            "fullName": _s(data.get("full_name")),
            "nationality": _s(data.get("nationality")),
            "passportCountry": _s(data.get("passport_country")),
            "passportExpiry": _s(data.get("passport_expiry")),
            "email": _s(data.get("email")),
        }
    )

    family_members: Dict[str, Any] = {
        "children": [
            _drop_none({"dateOfBirth": _s(c.get("dob")), "relationship": "child"})
            for c in children
        ],
    }
    if partner is not None:
        family_members["spouse"] = _drop_none(
            {
                "fullName": _s(partner.get("name")),
                "wantsToWork": True if partner.get("needs_work_permit") == "yes" else None,
            }
        )

    assignment_context = _drop_none(
        {
            "jobTitle": _s(data.get("job_title")),
            "contractType": _s(data.get("contract_type")),
            "contractStartDate": _s(data.get("contract_start")),
            "salaryBand": _s(data.get("salary_band")),
            "workLocation": _s(data.get("office_address")),
        }
    )

    return {
        "relocationBasics": relocation_basics,
        "employeeProfile": employee_profile,
        "familyMembers": family_members,
        "assignmentContext": assignment_context,
    }
