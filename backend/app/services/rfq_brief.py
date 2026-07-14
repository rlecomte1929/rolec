"""AIQ-1521 follow-up — the RFQ brief a vendor actually receives.

WHAT WAS WRONG
--------------
A vendor was sent the word "movers" plus one optional free-text string the employee may or may
not have typed. If they typed nothing, the vendor got `{}`. Meanwhile the platform already knew
the route (Paris, FR -> Oslo, NO) and the target date, and sent neither. There was no response
deadline, no request to confirm scope, no request for a breakdown.

WHY IT MATTERS MORE THAN IT LOOKS
---------------------------------
The whole point of AIQ-1521 is to learn whether a real supplier answers an RFQ. If we send them
"someone is moving, click here" and they don't reply, we would conclude "suppliers don't respond"
when the truth is "we asked badly". A weak brief doesn't just lose quotes — it produces a FALSE
VERDICT on the business model. Same failure mode as the dead magic link.

THE RULES
---------
* Facts come from the CASE, server-side. The employee is never asked to re-type what we already
  know, and the client is never trusted for it.
* Anything we genuinely do not know is rendered "Not specified" — never guessed. A mover pricing
  a job off an invented floor number is worse than one who knows we didn't ask.
* The expectations are explicit: confirm the route, itemise the price, say how long it is valid,
  and reply by a date.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# How long a vendor gets to answer. Short enough to be a real ask, long enough to be fair.
RESPONSE_WINDOW_DAYS = 7

NOT_SPECIFIED = "Not specified"

# What we ask EVERY vendor to come back with, whatever the service. This is the half that was
# missing entirely: the vendor was never told what a good answer looks like.
RESPONSE_EXPECTATIONS: List[str] = [
    "Confirm you cover this route and can meet the date.",
    "Give an itemised price — not just a single total — so it can be compared fairly.",
    "Tell us how long your quote stays valid.",
    "Flag anything you need that is missing below.",
]


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def respond_by(days: int = RESPONSE_WINDOW_DAYS) -> str:
    return (datetime.now(tz=timezone.utc) + timedelta(days=days)).date().isoformat()


def build_movers_requirements(
    case: Optional[Dict[str, Any]],
    employee_answers: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """The structured brief for a household move.

    `case` is the relocation_cases row — the source of truth for the route and the date.
    `employee_answers` is only the part the platform CANNOT know: the property, storage, and
    anything unusual to carry.
    """
    case = case or {}
    answers = employee_answers or {}

    route = {
        "from_city": _clean(case.get("home_city")),
        "from_country": _clean(case.get("home_country")),
        "to_city": _clean(case.get("host_city")),
        "to_country": _clean(case.get("host_country")),
    }

    target = case.get("target_start_date")
    if isinstance(target, (date, datetime)):
        target = target.isoformat()[:10]
    target = _clean(target)

    return {
        "service": "movers",
        "route": route,
        "target_date": target,
        "property": {
            "size": _clean(answers.get("property_size")),
            "floor": _clean(answers.get("floor")),
            "lift": answers.get("lift") if isinstance(answers.get("lift"), bool) else None,
        },
        "storage_needed": answers.get("storage_needed") if isinstance(answers.get("storage_needed"), bool) else None,
        "special_items": _clean(answers.get("special_items")),
        "notes": _clean(answers.get("notes")),
    }


def render_brief_lines(requirements: Dict[str, Any]) -> List[Dict[str, str]]:
    """Turn the structured requirements into the label/value rows a vendor reads.

    Unknowns render as "Not specified" rather than being dropped — a vendor needs to see what we
    did NOT tell them, so they can ask, instead of silently guessing.
    """
    req = requirements or {}
    if req.get("service") != "movers":
        # Unknown/legacy shape (e.g. the old {"notes": "..."}): show what there is, honestly.
        notes = _clean(req.get("notes"))
        return [{"label": "Details", "value": notes or NOT_SPECIFIED}]

    route = req.get("route") or {}
    frm = ", ".join([p for p in (route.get("from_city"), route.get("from_country")) if p]) or NOT_SPECIFIED
    to = ", ".join([p for p in (route.get("to_city"), route.get("to_country")) if p]) or NOT_SPECIFIED

    prop = req.get("property") or {}
    prop_bits = [
        prop.get("size"),
        f"floor {prop['floor']}" if prop.get("floor") else None,
        None if prop.get("lift") is None else ("lift available" if prop["lift"] else "no lift"),
    ]
    prop_str = ", ".join([p for p in prop_bits if p]) or NOT_SPECIFIED

    storage = req.get("storage_needed")
    storage_str = NOT_SPECIFIED if storage is None else ("Yes" if storage else "No")

    rows = [
        {"label": "Move from", "value": frm},
        {"label": "Move to", "value": to},
        {"label": "Target move date", "value": req.get("target_date") or NOT_SPECIFIED},
        {"label": "Property", "value": prop_str},
        {"label": "Storage needed", "value": storage_str},
        {"label": "Special items", "value": req.get("special_items") or NOT_SPECIFIED},
    ]
    if req.get("notes"):
        rows.append({"label": "Anything else", "value": req["notes"]})
    return rows
