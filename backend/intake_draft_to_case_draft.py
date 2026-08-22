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


# [AIQ-1885] Every top-level key this converter reads. Kept beside it so the
# can-convert check below cannot drift from what the mapping actually consumes;
# a test asserts the two agree by parsing this module's own source.
RECOGNISED_INTAKE_KEYS: frozenset = frozenset({
    "contract_start", "contract_type", "dest_city", "dest_country", "email",
    "full_name", "job_title", "members", "nationality", "office_address",
    "origin_city", "origin_country", "passport_country", "passport_expiry",
    "purpose", "salary_band", "second_nationality", "target_date",
})

# The canonical camelCase-nested CaseDraftDTO sections. A draft carrying these
# and none of the flat keys is the exact shape that reached production during the
# T18 campaign: stored verbatim, echoed back by GET, and unreadable here — so the
# submit guard later reported all six relocationBasics fields missing while they
# were plainly visible in the stored draft.
_CANONICAL_SECTIONS = ("relocationBasics", "employeeProfile", "familyMembers",
                       "assignmentContext")


def unreadable_draft_reason(data: Optional[Dict[str, Any]]) -> Optional[str]:
    """``None`` when this converter can read the draft, else why it cannot.

    Deliberately permissive. The wizard autosaves as the employee types, so a
    draft holding one key — or none at all, on the first debounce — is normal and
    must keep working. This only objects when a draft carries content and *not a
    single key the converter consumes*, which is the difference between "partially
    filled in" and "wrong shape entirely".
    """
    if not isinstance(data, dict) or not data:
        return None  # an empty first autosave is legitimate
    if RECOGNISED_INTAKE_KEYS & set(data):
        return None  # at least one usable key — a normal partial draft

    nested = [k for k in _CANONICAL_SECTIONS if k in data]
    if nested:
        return (
            "Intake draft is in the canonical nested CaseDraftDTO shape "
            f"({', '.join(nested)}), but this endpoint stores the wizard's FLAT "
            "snake_case draft. Send flat keys such as origin_country, dest_country, "
            "purpose, target_date — or PATCH /api/cases/{case_id} for the nested shape."
        )
    return (
        "Intake draft contains no keys this endpoint can read "
        f"(got: {', '.join(sorted(map(str, data))[:8])}). Expected flat snake_case "
        "wizard keys such as origin_country, dest_country, purpose, target_date."
    )


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
            # Carried because the requirements gate now classifies on BOTH: a dual national
            # holds the union of their rights, and judging a Venezuelan/Italian citizen on
            # whichever nationality intake recorded first puts them on a permit track they
            # must not apply for. The interview has always asked for this
            # (`q_has_second_nationality`) and stored it; the draft simply dropped it, so the
            # answer never reached the only place it mattered.
            "second_nationality": _s(data.get("second_nationality")),
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
