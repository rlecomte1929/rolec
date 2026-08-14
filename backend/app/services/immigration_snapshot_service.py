"""
Employee immigration snapshot — the "your move at a glance" payload for the
relocation assistant (Slice 2).

Surfaces, for ONE case, the proactive signals that today live only behind the
HR immigration panel: the risk flags (passport expiry, address gap, book-early,
dependent timing, …) and a checklist summary. Reuses the exact same engine the
HR panel uses (`get_requirements` / `evaluate_risks`) so the employee sees the
same risks — just scoped to their own case (the caller enforces ownership).

PII-safe: `RiskFlag` carries only severity/title/description/recommended_action/
deadline; raw profile identifiers (passport number, DOB) are never included.
Fail-closed: an unknown corridor or an unseeded corridor returns `covered=False`
rather than an empty checklist that reads as "nothing required".
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from .immigration_regime import default_visa_type_for_destination
from .immigration_requirement_service import RiskFlag, evaluate_risks, get_requirements
from .immigration_service import _get_case_details, _load_profile_for_case


def _serialize_risk(rf: RiskFlag) -> Dict[str, Any]:
    return {
        "flag_type": rf.flag_type,
        "severity": rf.severity,
        "title": rf.title,
        "description": rf.description,
        "recommended_action": rf.recommended_action,
        "deadline": rf.deadline.isoformat() if rf.deadline else None,
    }


def _uncovered(corridor_from, corridor_to, visa_type) -> Dict[str, Any]:
    return {
        "covered": False,
        "corridor_from": corridor_from,
        "corridor_to": corridor_to,
        "visa_type": visa_type,
        "risk_flags": [],
        "checklist_summary": {"total": 0, "required": 0, "conditional": 0},
    }


def build_immigration_snapshot(
    case_id: str, visa_type: Optional[str] = None
) -> Dict[str, Any]:
    """Build the proactive snapshot for a case. Ownership is the caller's job."""
    # org_id is unused by _get_case_details' query; ownership is enforced upstream.
    case = _get_case_details(case_id, "")
    corridor_from = (case or {}).get("origin_country")
    corridor_to = (case or {}).get("dest_country")

    # [AIQ-1833] Resolve the visa type from the destination rather than defaulting to
    # blue_card. This endpoint reaches the EMPLOYEE, so a wrong permit here is the
    # version of this bug that can actually mislead someone.
    if visa_type is None:
        visa_type = default_visa_type_for_destination(corridor_to)

    # Fail closed: missing geography cannot be answered authoritatively.
    if not corridor_from or not corridor_to:
        return _uncovered(corridor_from, corridor_to, visa_type)

    # Fail closed: a destination with no Blue Card and no explicit visa type cannot be
    # answered. Querying with visa_type=None would match nothing anyway.
    if not visa_type:
        return _uncovered(corridor_from, corridor_to, visa_type)

    requirements = get_requirements(corridor_from, corridor_to, visa_type)
    # Fail closed: an unseeded corridor returns no rows.
    if not requirements:
        return _uncovered(corridor_from, corridor_to, visa_type)

    profile = _load_profile_for_case(case_id)
    risk_flags = []
    if profile:
        move_date = None
        move_raw = profile.get("_move_date")
        if move_raw:
            try:
                move_date = date.fromisoformat(str(move_raw)[:10])
            except (ValueError, TypeError):
                move_date = None
        risk_flags = evaluate_risks(profile, requirements, move_date)

    required = sum(1 for r in requirements if getattr(r, "is_required", False))
    conditional = sum(1 for r in requirements if getattr(r, "is_conditional", False))

    return {
        "covered": True,
        "corridor_from": corridor_from,
        "corridor_to": corridor_to,
        "visa_type": visa_type,
        "risk_flags": [_serialize_risk(r) for r in risk_flags],
        "checklist_summary": {
            "total": len(requirements),
            "required": required,
            "conditional": conditional,
        },
    }
