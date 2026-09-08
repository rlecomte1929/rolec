"""Ask-once household facts derived from the wizard CaseDraftDTO.

Services questions, RFQ briefs, and wizard_cases denormalized columns all used to
read different slices (or defaults). This is the single derivation so a partner +
two children in intake cannot become people=2 and child_ages=8 downstream.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple


def marital_status(has_partner: bool, child_count: int) -> str:
    if has_partner and child_count:
        return "partner_kids"
    if has_partner:
        return "partner"
    if child_count:
        return "kids_only"
    return "solo"


def age_from_dob(dob: Any, today: Optional[date] = None) -> Optional[int]:
    if not dob:
        return None
    raw = str(dob).strip()[:10]
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        return None
    t = today or date.today()
    return t.year - d.year - ((t.month, t.day) < (d.month, d.day))


def _family(draft: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    fam = (draft or {}).get("familyMembers") or {}
    return fam if isinstance(fam, dict) else {}


def household_from_draft(draft: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Facts Services + RFQ should reuse instead of re-asking."""
    fam = _family(draft)
    spouse = fam.get("spouse") if isinstance(fam.get("spouse"), dict) else {}
    children = fam.get("children") if isinstance(fam.get("children"), list) else []
    kids = [c for c in children if isinstance(c, dict)]
    has_partner = bool(
        (spouse.get("fullName") or spouse.get("full_name") or "").strip()
        or (fam.get("maritalStatus") or "") in ("partner", "partner_kids", "Married", "Partnership")
    )
    ages: List[int] = []
    for c in kids:
        age = age_from_dob(c.get("dateOfBirth") or c.get("date_of_birth") or c.get("dob"))
        if age is not None and age >= 0:
            ages.append(age)
    child_n = len(kids)
    household_size = 1 + (1 if has_partner else 0) + child_n
    ctx = (draft or {}).get("assignmentContext") or {}
    commute = ctx.get("commuteMins")
    try:
        commute_mins = int(commute) if commute is not None and str(commute).strip() != "" else None
    except (TypeError, ValueError):
        commute_mins = None
    status = fam.get("maritalStatus") or marital_status(has_partner, child_n)
    return {
        "has_partner": has_partner,
        "child_count": child_n,
        "household_size": household_size,
        "child_ages": ages,
        "dependents_ages": ",".join(str(a) for a in ages) if ages else None,
        "marital_status": status,
        "commute_mins": commute_mins,
    }


def wizard_family_columns(draft: Optional[Dict[str, Any]]) -> Tuple[bool, int]:
    h = household_from_draft(draft)
    return bool(h["has_partner"]), int(h["child_count"])
