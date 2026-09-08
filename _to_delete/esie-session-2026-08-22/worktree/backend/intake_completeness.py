"""Pure intake-completeness helpers (no app/DB deps → unit-testable in isolation).

Used by the employee assignment-submit guard so an incomplete intake is rejected
server-side with a 4xx and a field-level error map (not just a generic string).
"""
from typing import Any, Dict, List

# Step-1 "relocation basics" required before a case can be submitted.
REQUIRED_INTAKE_BASICS: List[str] = [
    "originCountry",
    "originCity",
    "destCountry",
    "destCity",
    "purpose",
    "targetMoveDate",
]


def missing_intake_basics(draft: Dict[str, Any]) -> List[str]:
    """Return the required relocationBasics keys absent/empty in the wizard draft."""
    basics = (draft or {}).get("relocationBasics", {}) or {}
    return [k for k in REQUIRED_INTAKE_BASICS if not basics.get(k)]


def incomplete_intake_detail(missing: List[str]) -> Any:
    """HTTP 400 ``detail`` for an incomplete submit.

    Field-level map (``missingFields`` + ``suggestedStep``) when we can pinpoint
    the missing step-1 basics; a human-readable string otherwise.
    """
    if missing:
        return {
            "message": "Profile is not complete. Please complete the required wizard fields.",
            "missingFields": [f"relocationBasics.{k}" for k in missing],
            "suggestedStep": 1,
        }
    return (
        "Profile is not complete. Please complete all 5 wizard steps "
        "(Relocation Basics, Employee Profile, Family, Assignment Context) and try again."
    )
