"""Convert the wizard's flat snake_case intake draft → canonical camelCase case draft.

AIQ-1311 (P0). The v2 "Pathway" intake wizard autosaves a **flat snake_case**
``IntakeData`` blob into ``case_assignments.intake_draft`` (keyed by assignment_id,
written on every keystroke — the reliable store). The submit validator and the
HR-facing promotion, however, expect the **nested camelCase** ``relocationBasics.*``
shape produced by the frontend ``intakeToCaseDraft.ts``. The frontend only wrote
that camelCase shape to ``wizard_cases.draft_json`` — and often to the wrong
wizard_cases id — so submit read an empty draft and 400'd.

This is the **server-side twin of** ``frontend/src/features/platform-v2/intake/intakeToCaseDraft.ts``
so the backend submit can be authoritative: read the assignment draft, convert
here, validate, and promote — no dependency on the frontend patching the right id.

Mirrors the TS converter's output exactly (relocationBasics / employeeProfile /
familyMembers / assignmentContext) **and additionally carries the work-pattern /
commute fields the TS converter omits** (``work_pattern``, ``commute_mins``,
``commute_mode``).

Pure (stdlib only) so it unit-tests in isolation, same as ``intake_completeness.py``.
"""
from typing import Any, Dict, List, Optional


def _clean(value: Any) -> Optional[Any]:
    """Mirror the TS ``data.x || undefined`` — empty string/None drop out so the
    backend deep-merge never overwrites a good value with a blank."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def intake_draft_to_case_draft(snake: Dict[str, Any]) -> Dict[str, Any]:
    """Map a flat snake_case wizard intake draft onto the canonical nested
    camelCase case draft the submit validator + HR promotion consume."""
    data = snake or {}
    members: List[Dict[str, Any]] = data.get("members") or []

    partner = next((m for m in members if (m or {}).get("kind") == "partner"), None)
    child_members = [m for m in members if (m or {}).get("kind") == "child"]
    has_dependents = any((m or {}).get("kind") in ("partner", "child") for m in members)

    spouse: Optional[Dict[str, Any]] = None
    if partner:
        spouse = {
            "fullName": _clean(partner.get("name")),
            # TS: needs_work_permit === 'yes' || undefined
            "wantsToWork": True if partner.get("needs_work_permit") == "yes" else None,
        }

    children = [
        {
            "dateOfBirth": _clean((c or {}).get("dob")),
            "relationship": "child",
        }
        for c in child_members
    ]

    return {
        "relocationBasics": {
            "originCountry": _clean(data.get("origin_country")),
            "originCity": _clean(data.get("origin_city")),
            "destCountry": _clean(data.get("dest_country")),
            "destCity": _clean(data.get("dest_city")),
            "purpose": _clean(data.get("purpose")),
            "targetMoveDate": _clean(data.get("target_date")),
            "hasDependents": has_dependents,
        },
        "employeeProfile": {
            "fullName": _clean(data.get("full_name")),
            "nationality": _clean(data.get("nationality")),
            "passportCountry": _clean(data.get("passport_country")),
            "passportExpiry": _clean(data.get("passport_expiry")),
            "email": _clean(data.get("email")),
        },
        "familyMembers": {
            "spouse": spouse,
            "children": children,
        },
        "assignmentContext": {
            "jobTitle": _clean(data.get("job_title")),
            "contractType": _clean(data.get("contract_type")),
            "contractStartDate": _clean(data.get("contract_start")),
            "salaryBand": _clean(data.get("salary_band")),
            "workLocation": _clean(data.get("office_address")),
            # Carried through from the wizard but omitted by intakeToCaseDraft.ts:
            "workPattern": _clean(data.get("work_pattern")),
            "commuteMins": _clean(data.get("commute_mins")),
            "commuteMode": _clean(data.get("commute_mode")),
        },
    }
