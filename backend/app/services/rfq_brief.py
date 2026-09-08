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


def _canonical_service_key(raw: Optional[str]) -> str:
    k = (raw or "").strip().lower()
    if k in ("living_areas", "housing_agencies", "housing"):
        return "housing"
    if k in ("moving", "movers"):
        return "movers"
    return k


def _route_and_date(case: Optional[Dict[str, Any]], draft: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    case = case or {}
    basics = ((draft or {}).get("relocationBasics") or {}) if isinstance(draft, dict) else {}
    target = case.get("target_start_date") or basics.get("targetMoveDate")
    if isinstance(target, (date, datetime)):
        target = target.isoformat()[:10]
    return {
        "from_city": _clean(case.get("home_city") or basics.get("originCity")),
        "from_country": _clean(case.get("home_country") or basics.get("originCountry")),
        "to_city": _clean(case.get("host_city") or basics.get("destCity")),
        "to_country": _clean(case.get("host_country") or basics.get("destCountry")),
        "target_date": _clean(target),
    }


def build_movers_requirements(
    case: Optional[Dict[str, Any]],
    employee_answers: Optional[Dict[str, Any]] = None,
    draft: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """The structured brief for a household move.

    `case` is the relocation_cases row — the source of truth for the route and the date.
    `employee_answers` is only the part the platform CANNOT know: the property, storage, and
    anything unusual to carry. Household size comes from intake, never from a second form.
    """
    answers = employee_answers or {}
    rd = _route_and_date(case, draft)
    from .household_from_draft import household_from_draft

    hh = household_from_draft(draft)
    people = answers.get("people")
    try:
        people_n = int(people) if people is not None else hh.get("household_size")
    except (TypeError, ValueError):
        people_n = hh.get("household_size")

    return {
        "service": "movers",
        "route": {
            "from_city": rd["from_city"],
            "from_country": rd["from_country"],
            "to_city": rd["to_city"],
            "to_country": rd["to_country"],
        },
        "target_date": rd["target_date"],
        "household_size": people_n,
        "property": {
            "size": _clean(answers.get("property_size") or answers.get("acc_type")),
            "floor": _clean(answers.get("floor")),
            "lift": answers.get("lift") if isinstance(answers.get("lift"), bool) else None,
        },
        "storage_needed": answers.get("storage_needed") if isinstance(answers.get("storage_needed"), bool) else None,
        "special_items": _clean(answers.get("special_items")),
        "packing": _clean(answers.get("packing")),
        "notes": _clean(answers.get("notes")),
        "cover_note": _clean(answers.get("cover_note") or answers.get("message_body")),
    }


def build_housing_requirements(
    case: Optional[Dict[str, Any]],
    employee_answers: Optional[Dict[str, Any]] = None,
    draft: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    answers = employee_answers or {}
    rd = _route_and_date(case, draft)
    from .household_from_draft import household_from_draft

    hh = household_from_draft(draft)
    commute = answers.get("commute_mins")
    if commute is None:
        commute = hh.get("commute_mins")
    return {
        "service": "housing",
        "route": {
            "from_city": rd["from_city"],
            "from_country": rd["from_country"],
            "to_city": rd["to_city"],
            "to_country": rd["to_country"],
        },
        "target_date": rd["target_date"],
        "household_size": hh.get("household_size"),
        "bedrooms": answers.get("bedrooms") or answers.get("acc_bedrooms"),
        "commute_mins": commute,
        "budget_min": answers.get("budget_min"),
        "budget_max": answers.get("budget_max"),
        "housing_cap": answers.get("housing_cap"),
        "notes": _clean(answers.get("notes")),
        "cover_note": _clean(answers.get("cover_note") or answers.get("message_body")),
    }


def build_schools_requirements(
    case: Optional[Dict[str, Any]],
    employee_answers: Optional[Dict[str, Any]] = None,
    draft: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    answers = employee_answers or {}
    rd = _route_and_date(case, draft)
    from .household_from_draft import household_from_draft

    hh = household_from_draft(draft)
    ages = answers.get("child_ages")
    if not ages:
        ages = hh.get("dependents_ages")
    return {
        "service": "schools",
        "route": {
            "to_city": rd["to_city"],
            "to_country": rd["to_country"],
        },
        "target_date": rd["target_date"],
        "child_ages": ages,
        "school_type": _clean(answers.get("school_type") or answers.get("curriculum")),
        "notes": _clean(answers.get("notes")),
        "cover_note": _clean(answers.get("cover_note") or answers.get("message_body")),
    }


def build_requirements_for_service(
    service_key: str,
    case: Optional[Dict[str, Any]],
    employee_answers: Optional[Dict[str, Any]] = None,
    draft: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    key = _canonical_service_key(service_key)
    if key == "movers":
        return build_movers_requirements(case, employee_answers, draft)
    if key == "housing":
        return build_housing_requirements(case, employee_answers, draft)
    if key == "schools":
        return build_schools_requirements(case, employee_answers, draft)
    answers = employee_answers or {}
    out = {"service": key, "notes": _clean(answers.get("notes"))}
    cover = _clean(answers.get("cover_note") or answers.get("message_body"))
    if cover:
        out["cover_note"] = cover
    return out


def draft_supplier_message(
    *,
    case: Optional[Dict[str, Any]] = None,
    draft: Optional[Dict[str, Any]] = None,
    service_keys: Optional[List[str]] = None,
    supplier_names: Optional[List[str]] = None,
) -> str:
    """Plain-language RFQ cover the employee reviews before send. No child names."""
    from .household_from_draft import household_from_draft

    rd = _route_and_date(case, draft)
    hh = household_from_draft(draft)
    frm = ", ".join([p for p in (rd["from_city"], rd["from_country"]) if p]) or NOT_SPECIFIED
    to = ", ".join([p for p in (rd["to_city"], rd["to_country"]) if p]) or NOT_SPECIFIED
    when = rd["target_date"] or NOT_SPECIFIED
    size = hh.get("household_size") or 1
    ages = hh.get("child_ages") or []
    age_bit = f", children aged {', '.join(str(a) for a in ages)}" if ages else ""
    keys = [_canonical_service_key(k) for k in (service_keys or [])]
    labels = {
        "housing": "housing / neighbourhood search",
        "movers": "an international household move",
        "schools": "school search",
        "banks": "banking setup",
        "insurances": "insurance",
        "electricity": "utilities",
    }
    wanted = [labels.get(k, k) for k in keys if k]
    if not wanted:
        wanted = ["relocation support"]
    who = ", ".join(supplier_names) if supplier_names else "you"
    lines = [
        f"Hello,",
        "",
        f"ReloPass is requesting a quotation on behalf of an employee relocating from {frm} to {to} "
        f"(target date {when}).",
        "",
        f"Household: {size} people{age_bit}.",
        "",
        f"We would like pricing for: {', '.join(wanted)}.",
        "",
        "Please confirm you can cover this request, send an itemised price (not a single lump sum), "
        f"and say how long the quote stays valid. Reply by {respond_by()}.",
        "",
        f"This draft was prepared from the employee's intake for {who}. They will review it before it is sent.",
    ]
    return "\n".join(lines)


def render_brief_lines(requirements: Dict[str, Any]) -> List[Dict[str, str]]:
    """Turn the structured requirements into the label/value rows a vendor reads.

    Unknowns render as "Not specified" rather than being dropped — a vendor needs to see what we
    did NOT tell them, so they can ask, instead of silently guessing.
    """
    req = requirements or {}
    service = req.get("service")
    cover = _clean(req.get("cover_note"))
    extra: List[Dict[str, str]] = []
    if cover:
        extra.append({"label": "Message", "value": cover})

    if service == "housing":
        route = req.get("route") or {}
        to = ", ".join([p for p in (route.get("to_city"), route.get("to_country")) if p]) or NOT_SPECIFIED
        rows = [
            {"label": "Destination", "value": to},
            {"label": "Target date", "value": req.get("target_date") or NOT_SPECIFIED},
            {"label": "Household size", "value": str(req.get("household_size") or NOT_SPECIFIED)},
            {"label": "Bedrooms", "value": str(req.get("bedrooms") or NOT_SPECIFIED)},
            {"label": "Max commute (min)", "value": str(req.get("commute_mins") or NOT_SPECIFIED)},
        ]
        return rows + extra

    if service == "schools":
        route = req.get("route") or {}
        to = ", ".join([p for p in (route.get("to_city"), route.get("to_country")) if p]) or NOT_SPECIFIED
        rows = [
            {"label": "City", "value": to},
            {"label": "Target date", "value": req.get("target_date") or NOT_SPECIFIED},
            {"label": "Children's ages", "value": str(req.get("child_ages") or NOT_SPECIFIED)},
            {"label": "School type", "value": req.get("school_type") or NOT_SPECIFIED},
        ]
        return rows + extra

    if service != "movers":
        # Unknown/legacy shape (e.g. the old {"notes": "..."}): show what there is, honestly.
        notes = _clean(req.get("notes"))
        rows = [{"label": "Details", "value": notes or NOT_SPECIFIED}]
        return rows + extra

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
        {"label": "Household size", "value": str(req.get("household_size") or NOT_SPECIFIED)},
        {"label": "Property", "value": prop_str},
        {"label": "Storage needed", "value": storage_str},
        {"label": "Special items", "value": req.get("special_items") or NOT_SPECIFIED},
    ]
    if req.get("notes"):
        rows.append({"label": "Anything else", "value": req["notes"]})
    return rows + extra
