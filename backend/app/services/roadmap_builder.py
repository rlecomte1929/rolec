"""
Roadmap builder service — GAP 2 (multi-track plan) and GAP 5 (Pathway V2 backend).

Ports the ``deriveTimeline`` pure function from pathway-v2-data.js into Python,
producing a server-side roadmap from a wizard_cases draft.

Track grouping mirrors the Pathway V2 UX:
  - Visa & Permit   (immigration-related steps)
  - Civil Documents (origin-side docs, apostilles, translations)
  - Family          (dependent-specific steps, conditional on household)
  - Settlement      (housing, police reg, tax, school, settle-in)

Returns a RoadmapResponse dict — no DB write, pure computation.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .immigration_regime import ImmigrationRegimeRouter
from .requirements_purpose_key import assignment_type_from_purpose
from .roadmap_corridor_overlay import corridor_overlay
from .wizard_draft_mapper import extract_profile_from_wizard_draft

logger = logging.getLogger(__name__)

# Regimes that require no visa/permit — the Visa & Permit track is omitted for
# these (EU/EEA free movement, and same-country domestic moves).
_NO_VISA_REGIMES = frozenset({"eu_free_movement", "domestic"})


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    return "".join(p[0].upper() for p in parts[:2])


def _first_name(name: str) -> str:
    return name.split()[0] if name else ""


def _age_from_dob(dob: Optional[str]) -> Optional[int]:
    if not dob:
        return None
    try:
        b = date.fromisoformat(dob)
        today = date.today()
        age = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
        return age
    except (ValueError, TypeError):
        return None


def _label_for_housing(key: Optional[str]) -> str:
    mapping = {
        "city_centre": "City centre",
        "suburb": "Suburb",
        "near_school": "Near international school",
        "flexible": "Flexible",
    }
    return mapping.get(key or "", key or "")


# ─────────────────────────────────────────────────────────────────────────────
# Step builders
# ─────────────────────────────────────────────────────────────────────────────

def _build_visa_track(case: Dict[str, Any]) -> Dict[str, Any]:
    """Visa & Permit track — 2 main steps."""
    draft = case.get("draft", {})
    basics = draft.get("relocationBasics", {})
    dest = basics.get("destCountry", "the destination country")
    employer = draft.get("assignmentContext", {}).get("employerName", "Your employer")
    status = case.get("status", "created")

    step1_status = "active" if status == "open" else "locked"

    return {
        "id": "visa",
        "name": "Visa & Permit",
        "icon": "passport",
        "steps": [
            {
                "n": 1,
                "key": "sponsorship",
                "title": "Employer sponsorship letter",
                "status": step1_status,
                "owner": "Employer",
                "where": "Origin / Remote",
                "time": "1–2 weeks",
                "cost": "Covered",
                "depends": None,
                "line": f"{employer} submits a sponsorship declaration to the {dest} immigration authority.",
                "subs": [
                    "HR confirms salary threshold",
                    "HR uploads employment contract",
                    "Letter issued",
                ],
                "waitingNote": f"No action required. Waiting on {employer}.",
            },
            {
                "n": 2,
                "key": "permit",
                "title": "Work / residence permit application",
                "status": "locked",
                "owner": "You + Employer",
                "where": "Online (immigration authority)",
                "time": "3–6 weeks",
                "cost": "€400–€800",
                "depends": "Step 1",
                "line": "Submit the permit application using the employer sponsorship letter.",
                "subs": [
                    "Create applicant account on immigration portal",
                    "Upload passport copy",
                    "Pay application fee",
                    "Submit form",
                ],
            },
        ],
    }


def _build_civil_track(case: Dict[str, Any]) -> Dict[str, Any]:
    """Civil Documents track — origin-side paperwork."""
    draft = case.get("draft", {})
    basics = draft.get("relocationBasics", {})
    origin = basics.get("originCountry", "origin country")
    family = draft.get("familyMembers", {})
    marital = family.get("maritalStatus", "solo")
    has_spouse = marital in ("partner", "partner_kids")

    subs_birth = [
        "Obtain apostilled birth certificate",
        "Certified translation if required",
    ]
    subs_civil = [
        "Apostilled marriage certificate",
        "Proof of address (last 3 months)",
    ] if has_spouse else [
        "Proof of address (last 3 months)",
    ]

    return {
        "id": "civil",
        "name": "Civil Documents",
        "icon": "document",
        "steps": [
            {
                "n": 3,
                "key": "docs-origin",
                "title": f"Document gathering — {origin} side",
                "status": "locked",
                "owner": "You",
                "where": f"{origin} (local)",
                "time": "2–3 weeks",
                "cost": "€60–€120",
                "depends": "Parallel with Visa Step 2",
                "line": f"Collect apostilled civil documents in {origin} before departure.",
                "subs": subs_birth + subs_civil,
            },
        ],
    }


def _build_family_track(case: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Family track — only present when dependents exist."""
    draft = case.get("draft", {})
    family = draft.get("familyMembers", {})
    marital = family.get("maritalStatus", "solo")
    has_spouse = marital in ("partner", "partner_kids")
    has_kids = marital in ("partner_kids", "kids_only")

    if not has_spouse and not has_kids:
        return None

    steps = []
    n = 4

    if has_spouse:
        spouse = family.get("spouse") or {}
        spouse_name = spouse.get("fullName", "Your partner")
        steps.append({
            "n": n,
            "key": "spouse-permit",
            "title": f"Dependent permit — {_first_name(spouse_name)}",
            "status": "locked",
            "owner": f"You + {_first_name(spouse_name)}",
            "where": "Online",
            "time": "2–4 weeks",
            "cost": "€200–€400",
            "depends": "Visa Step 2",
            "line": "Dependent family members need their own permit linked to the primary applicant.",
            "subs": [
                "Submit dependent permit application",
                f"Upload {_first_name(spouse_name)}'s passport and civil documents",
                "Confirm right-to-work status if applicable",
            ],
            "member": {
                "name": spouse_name,
                "initials": _initials(spouse_name),
                "label": "Partner",
            },
        })
        n += 1

    if has_kids:
        children = family.get("children") or []
        # Include known family from HR if no children set yet
        known_children = (draft.get("knownFamily") or {}).get("children") or []
        all_kids = children if children else known_children

        for child in all_kids:
            child_name = child.get("fullName", "Child")
            dob = child.get("dateOfBirth")
            age = _age_from_dob(dob)
            age_label = f", {age}" if age is not None else ""
            steps.append({
                "n": n,
                "key": f"child-permit-{_initials(child_name).lower()}",
                "title": f"Child documents — {_first_name(child_name)}",
                "status": "locked",
                "owner": "You",
                "where": "Origin country",
                "time": "1–2 weeks",
                "cost": "Covered",
                "depends": "Civil Docs Step 3",
                "line": f"Gather {_first_name(child_name)}'s documents for dependent permit and school enrolment.",
                "subs": [
                    "Birth certificate + apostille",
                    "Vaccination records",
                    "School records from previous school",
                ],
                "member": {
                    "name": child_name,
                    "initials": _initials(child_name),
                    "label": f"Child{age_label}",
                },
            })
            n += 1

    if not steps:
        return None

    return {
        "id": "family",
        "name": "Family",
        "icon": "family",
        "steps": steps,
    }


def _build_settlement_track(case: Dict[str, Any]) -> Dict[str, Any]:
    """Settlement track — housing, police reg, tax, school, settle-in."""
    draft = case.get("draft", {})
    basics = draft.get("relocationBasics", {})
    family = draft.get("familyMembers", {})
    marital = family.get("maritalStatus", "solo")
    has_kids = marital in ("partner_kids", "kids_only")
    housing_pref = basics.get("housingPreference")
    dest_city = basics.get("destCity", "destination city")
    dest_country = basics.get("destCountry", "destination country")

    housing_filter = f" — {_label_for_housing(housing_pref)} filter applied" if housing_pref else ""

    steps = [
        {
            "n": 5,
            "key": "housing",
            "title": "Housing search",
            "status": "locked",
            "owner": "You",
            "where": f"{dest_city} (remote OK)",
            "time": "2–4 weeks",
            "cost": "Variable",
            "depends": "Visa Step 2 approved",
            "line": "Most landlords require a permit reference or employer letter.",
            "subs": [
                "Contact HR relocation contact",
                f"Property search{housing_filter}",
                "Sign lease",
            ],
        },
        {
            "n": 6,
            "key": "police",
            "title": f"Registration on arrival — {dest_country}",
            "status": "locked",
            "owner": "You",
            "where": f"Local authority in {dest_city}",
            "time": "1 week",
            "cost": "—",
            "depends": "Permit approved + arrival",
            "line": "Register with local authorities within the required timeframe after arrival.",
            "subs": [
                "Book appointment online",
                "Bring: passport, rental contract, employer letter",
                "Receive registration certificate",
            ],
        },
        {
            "n": 7,
            "key": "tax",
            "title": "Tax / social number registration",
            "status": "locked",
            "owner": "You",
            "where": "Tax authority",
            "time": "1–2 weeks",
            "cost": "—",
            "depends": "Police registration (Step 6)",
            "line": "A local tax or national ID number is required before payroll can be processed.",
            "subs": [
                "Submit application with registration certificate",
                "Receive number by post or online",
                "Provide to employer payroll",
            ],
        },
    ]

    if has_kids:
        children = family.get("children") or []
        known_children = (draft.get("knownFamily") or {}).get("children") or []
        all_kids = children if children else known_children
        first_child = all_kids[0] if all_kids else {}
        child_name = _first_name(first_child.get("fullName", "child"))

        steps.append({
            "n": 8,
            "key": "school",
            "title": f"School enrolment — {dest_city} international",
            "status": "locked",
            "owner": "You",
            "where": dest_city,
            "time": "2–4 weeks",
            "cost": "Variable",
            "depends": "Housing (Step 5)",
            "line": "International school applications typically open year-round; local public school via municipality.",
            "subs": [
                "Research international school options",
                "Submit application with school records",
                f"Confirm start date with school for {child_name}",
            ],
        })

    steps.append({
        "n": 9 if has_kids else 8,
        "key": "settle",
        "title": "Settle-in essentials",
        "status": "locked",
        "owner": "You",
        "where": dest_city,
        "time": "Ongoing",
        "cost": "Variable",
        "depends": "Arrival",
        "line": "Practical setup: bank account, SIM, GP registration.",
        "subs": [
            "Open local bank account (tax number required)",
            "Register with local GP / healthcare",
            "Set up utilities and local services",
        ],
    })

    steps.append({
        "n": len(steps) + 5,
        "key": "close",
        "title": "Case close-out",
        "status": "locked",
        "owner": "HR",
        "where": "ReloPass",
        "time": "—",
        "cost": "—",
        "depends": "All steps complete",
        "line": "HR marks the case as Arrived and archives the policy record.",
        "subs": [],
    })

    return {
        "id": "settlement",
        "name": "Settlement",
        "icon": "home",
        "steps": steps,
    }


def _build_return_track(case: Dict[str, Any]) -> Dict[str, Any]:
    """Return & repatriation track — the round-trip back half of the journey.

    Skeleton scaffold per ``docs/otto/journey-completion-brief-2026-09-10.md`` (P10): the
    highest-value steps every temporary assignment ends with. Steps are generic and
    ``locked`` until the assignment nears its end; reverse-corridor requirement facts
    (host-exit, home re-registration, social/pension switch-back) enrich them later the
    same way ``_apply_corridor_overlay`` enriches the outbound tracks. Omitted for a
    PERMANENT relocation, which has no return (see ``_return_track_applies``).
    """
    draft = case.get("draft", {})
    basics = draft.get("relocationBasics", {})
    origin_country = basics.get("originCountry") or basics.get("origin_country") or "home country"
    dest_country = basics.get("destCountry", "destination country")

    steps = [
        {
            "n": 20,
            "key": "return-review",
            "title": "End-of-assignment review",
            "status": "locked",
            "owner": "HR",
            "where": "ReloPass",
            "time": "~6 months before end",
            "cost": "—",
            "depends": "Assignment nearing end",
            "line": "HR and the employee plan the return: next role, timing, and what the return covers.",
            "subs": [
                "Confirm assignment end date",
                "Agree return or onward-transfer destination",
                "Review return entitlements in the policy",
            ],
        },
        {
            "n": 21,
            "key": "return-host-exit",
            "title": f"Close registrations & tax in {dest_country}",
            "status": "locked",
            "owner": "You",
            "where": f"{dest_country} authorities",
            "time": "2–6 weeks",
            "cost": "—",
            "depends": "End-of-assignment review",
            "line": "De-register locally and settle the final host-country tax filing before leaving.",
            "subs": [
                "De-register your address / residence",
                "File the final host-country tax return",
                "Close or convert local accounts and utilities",
            ],
        },
        {
            "n": 22,
            "key": "return-home-reentry",
            "title": f"Re-register in {origin_country}",
            "status": "locked",
            "owner": "You",
            "where": f"{origin_country} authorities",
            "time": "1–3 weeks",
            "cost": "—",
            "depends": "Arrival home",
            "line": "Re-establish home-country residence: address, healthcare, and tax residence.",
            "subs": [
                "Re-register your address",
                "Re-activate home healthcare cover",
                "Confirm tax-residence status on return",
            ],
        },
        {
            "n": 23,
            "key": "return-social",
            "title": "Social security & pension switch-back",
            "status": "locked",
            "owner": "You",
            "where": "Home social-security body",
            "time": "2–4 weeks",
            "cost": "—",
            "depends": "Re-registration",
            "line": "Move social-security and pension cover back to the home scheme; close any A1 / certificate of coverage.",
            "subs": [
                "Notify the home social-security scheme",
                "Confirm pension continuity across the assignment",
                "Close the A1 / certificate of coverage",
            ],
        },
        {
            "n": 24,
            "key": "return-move",
            "title": "Return move & storage release",
            "status": "locked",
            "owner": "You",
            "where": f"{dest_country} → {origin_country}",
            "time": "4–8 weeks",
            "cost": "Variable",
            "depends": "End-of-assignment review",
            "line": "Book the return shipment and release anything left in storage at origin.",
            "subs": [
                "Get return-move quotes",
                "Schedule packing and shipment",
                "Release goods from storage",
            ],
        },
        {
            "n": 25,
            "key": "return-close",
            "title": "Return case close-out",
            "status": "locked",
            "owner": "HR",
            "where": "ReloPass",
            "time": "—",
            "cost": "—",
            "depends": "All return steps complete",
            "line": "HR marks the assignment as Repatriated and archives the return record.",
            "subs": [],
        },
    ]

    return {
        "id": "return",
        "name": "Return & repatriation",
        "icon": "return",
        "steps": steps,
    }


def _build_predeparture_track(case: Dict[str, Any]) -> Dict[str, Any]:
    """Pre-departure track — the home-country obligations to close before leaving.

    The front half of the round-trip and the mirror of ``_build_return_track``: home
    tax residency, de-registration from the home population/municipal register, the
    social-security & health switch-over, and winding down home finances. Generic and
    ``locked``; where a corridor authors its own origin-exit steps (e.g. NO→FR's
    Folkeregister / folketrygden / exit-year return), ``_apply_corridor_overlay`` routes
    them into this track and supersedes the matching placeholders below — the same
    overlay mechanism the outbound tracks use. Omitted for a same-country move
    (see ``_predeparture_track_applies``).
    """
    draft = case.get("draft", {})
    basics = draft.get("relocationBasics", {})
    origin_country = basics.get("originCountry") or basics.get("origin_country") or "home country"

    steps = [
        {
            "n": 1,
            "key": "predep-review",
            "title": "Plan your departure",
            "status": "locked",
            "owner": "You + HR",
            "where": "ReloPass",
            "time": "~2 months before move",
            "cost": "—",
            "depends": None,
            "line": "Work through the home-country obligations to close before you leave — some have deadlines tied to your departure date.",
            "subs": [
                "Confirm your departure date",
                "List home registrations, tax and social-security to close",
                "Check which items have a deadline tied to leaving",
            ],
        },
        {
            "n": 2,
            "key": "predep-tax",
            "title": f"Close tax residency in {origin_country}",
            "status": "locked",
            "owner": "You",
            "where": f"{origin_country} tax authority",
            "time": "Varies",
            "cost": "—",
            "depends": "Departure planning",
            "line": "Notify the home tax authority of your move and check any exit-year filing — tax residence may not end on the physical move.",
            "subs": [
                "Notify the home tax authority of your departure",
                "Check whether an exit-year or split-year return is due",
                "Keep the access you need to file remotely after leaving",
            ],
        },
        {
            "n": 3,
            "key": "predep-deregister",
            "title": f"De-register from {origin_country}",
            "status": "locked",
            "owner": "You",
            "where": f"{origin_country} authorities",
            "time": "Varies",
            "cost": "—",
            "depends": "Departure planning",
            "line": "Report your move abroad to the home population / municipal register where one exists — some carry a short deadline after departure.",
            "subs": [
                "Report the move abroad to the population / municipal register",
                "Note any deadline tied to your departure date",
                "Keep proof of de-registration for the destination",
            ],
        },
        {
            "n": 4,
            "key": "predep-social",
            "title": "Transfer social security & health cover",
            "status": "locked",
            "owner": "You",
            "where": "Home social-security body",
            "time": "Varies",
            "cost": "—",
            "depends": "Departure planning",
            "line": "Move social-security and health cover to the destination scheme, and mind the gap so you are never uninsured in between.",
            "subs": [
                "End or transfer home social-security membership",
                "Handle your EHIC / certificate of coverage",
                "Line up destination cover so there is no gap",
            ],
        },
        {
            "n": 5,
            "key": "predep-financial",
            "title": "Preserve financial access & wind down accounts",
            "status": "locked",
            "owner": "You",
            "where": f"{origin_country}",
            "time": "Varies",
            "cost": "—",
            "depends": "Departure planning",
            "line": "Wind down home accounts and utilities — but keep one account open until any tax refund or final settlement clears.",
            "subs": [
                "Keep one home account open for refunds / final settlement",
                "Redirect or close utilities and subscriptions",
                "Update addresses and payment methods",
            ],
        },
    ]

    return {
        "id": "predeparture",
        "name": "Pre-departure",
        "icon": "departure",
        "steps": steps,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Requirements gating
# ─────────────────────────────────────────────────────────────────────────────

def _visa_track_required(draft: Dict[str, Any]) -> bool:
    """
    AIQ-972: requirements-driven roadmap. Detect the immigration regime from the
    wizard draft and decide whether the Visa & Permit track applies.

    Returns False for EU/EEA free-movement and domestic (same-country) moves —
    those need registration only, not a visa/permit — so the visa track is
    dropped, yielding a lighter, accurate plan. Returns True otherwise (incl.
    "unknown", so an incomplete draft keeps the visa track — fail-open).
    """
    profile = extract_profile_from_wizard_draft(draft)
    regime = ImmigrationRegimeRouter().detect_regime(
        nationality=profile.get("nationality"),
        destination_country=profile.get("destination_country"),
        origin_country=profile.get("origin_country"),
        contract_type=profile.get("contract_type"),
    )
    return regime.regime_id not in _NO_VISA_REGIMES


def _return_track_applies(draft: Dict[str, Any]) -> bool:
    """The Return & repatriation track applies to every temporary assignment.

    Omitted only for an explicit PERMANENT relocation, which has no return. An absent
    assignment type defaults to temporary (mirrors the LTA default in roadmap_generator),
    so an incomplete draft keeps the track — fail-open toward showing the full arc.
    """
    ac = draft.get("assignmentContext") or {}
    raw = ac.get("assignmentType")
    at = str(raw).strip().upper() if isinstance(raw, str) and raw.strip() else ""
    if not at:
        # Same hole as cases_write: many drafts store lta/sta/permanent in purpose.
        recovered = assignment_type_from_purpose(
            (draft.get("relocationBasics") or {}).get("purpose")
        )
        at = (recovered or "").upper()
    return at != "PERMANENT"


def _predeparture_track_applies(draft: Dict[str, Any]) -> bool:
    """Pre-departure home-exit obligations apply to every cross-border move.

    Omitted only for a same-country (domestic) move, which has no home country to
    leave. A missing origin or destination keeps the track — fail-open toward showing
    the full arc, mirroring ``_return_track_applies``.
    """
    basics = draft.get("relocationBasics") or {}
    origin = (basics.get("originCountry") or basics.get("origin_country") or "").strip().upper()
    dest = (basics.get("destCountry") or basics.get("dest_country") or "").strip().upper()
    return not (origin and dest and origin == dest)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def derive_roadmap(case: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure function: takes a wizard case dict (same shape as GET /api/cases/{id})
    and returns a RoadmapResponse dict.

    Equivalent to ``window.PATHWAY_V2.deriveTimeline`` in the frontend prototype.
    """
    draft = case.get("draft", {})
    basics = draft.get("relocationBasics", {})
    family = draft.get("familyMembers", {})
    marital = family.get("maritalStatus", "solo")
    has_kids = marital in ("partner_kids", "kids_only")
    has_spouse = marital in ("partner", "partner_kids")

    # Build tracks. AIQ-972: the Visa & Permit track is requirements-driven —
    # omitted for EU/EEA free-movement and domestic moves (no visa/permit needed).
    tracks: List[Dict[str, Any]] = []
    # Front half of the round-trip — the home-country obligations to close before
    # leaving. First in the arc; omitted for a same-country move (nothing to leave).
    if _predeparture_track_applies(draft):
        tracks.append(_build_predeparture_track(case))
    if _visa_track_required(draft):
        tracks.append(_build_visa_track(case))
    tracks.append(_build_civil_track(case))
    family_track = _build_family_track(case)
    if family_track:
        tracks.append(family_track)
    tracks.append(_build_settlement_track(case))
    # Round-trip back half — the return/repatriation skeleton (journey-completion brief P10).
    # Omitted for a PERMANENT relocation, which has no return.
    if _return_track_applies(draft):
        tracks.append(_build_return_track(case))

    # Outcome labels
    outcomes = ["Right to live and work in destination", "Civil registration complete"]
    if _predeparture_track_applies(draft):
        outcomes.insert(0, "Home-country obligations closed")
    if has_spouse:
        outcomes.append("Partner registered")
    if has_kids:
        outcomes.append("Children enrolled in school")
    if _return_track_applies(draft):
        outcomes.append("Return / repatriation planned")

    # Time estimate (rough based on destination)
    dest = (basics.get("destCountry") or "").upper()
    time_estimate = "12–16 weeks" if dest in ("US", "AU", "JP", "SG", "CA") else "8–14 weeks"

    # Cost estimate
    cost_estimate = "€600–€900"

    # Employer covers note
    employer = (draft.get("assignmentContext") or {}).get("employerName", "Your employer")

    # AIQ-1867: fold in the corridor's authored step graph where one exists. Until now the only
    # reader of corridors/<id>/pathways/*.yaml was the HR feasibility widget, so the employee
    # never saw the entry visa, the family route or the real durations. None => unchanged.
    advisories: List[Dict[str, Any]] = []
    overlay = corridor_overlay(case)
    if overlay:
        _apply_corridor_overlay(tracks, overlay)
        advisories = overlay["advisories"]
        # The authored critical path beats a guess keyed off the destination country.
        time_estimate = overlay["time_estimate"]

    return {
        "totals": {
            "time": time_estimate,
            "cost": cost_estimate,
            "employerCovers": f"{employer} covers sponsorship and immigration fees",
        },
        "outcomes": outcomes,
        "tracks": tracks,
        # Corridor exception cases. Empty unless the corridor declares them.
        "advisories": advisories,
        # Flat steps list for Pathway V2 compatibility (legacy shape)
        "steps": _flatten_steps(tracks),
        # Family parallel lanes (Pathway V2 shape)
        "lanes": _build_lanes(case),
    }


def _apply_corridor_overlay(
    tracks: List[Dict[str, Any]], overlay: Dict[str, Any]
) -> None:
    """Append the corridor's steps to their tracks, in the order the pathway declares them.

    Injected steps keep a ``corridor-`` key prefix so a consumer can tell authored corridor
    content from the generic scaffold, and each carries its provenance — the corridor files
    describe themselves as REPRESENTATIVE and not SME-verified, and a duration a family plans
    around must not render as established fact.
    """
    # Drop the generic scaffold steps the corridor supersedes, before appending. A plan that
    # says both "each dependent needs their own permit" and "the spouse may work on Stamp 1G
    # without a separate permit" is worse than one that only said the first.
    superseded = set(overlay.get("superseded_generic_keys") or ())
    if superseded:
        for track in tracks:
            track["steps"] = [
                s for s in track.get("steps", []) if s.get("key") not in superseded
            ]

    by_id = {t["id"]: t for t in tracks}
    for step in overlay["corridor_steps"]:
        # A corridor step whose intended track does not exist must still be rendered.
        # `_TRACK_BY_STEP` routes JOB_OFFER_CONTRACT and TRAVEL_TO_IE to "visa", and
        # `_visa_track_required` builds no visa track for a free mover — so those two were
        # dropped here by a bare `continue`, while `corridor_overlay` had already counted
        # them into the journey. Signing a contract and boarding a plane are not immigration
        # acts; they happen whatever the passport says. Settlement is built unconditionally,
        # so it is the safe home. Dropping a computed step is never right: it makes the
        # roadmap disagree with its own totals, silently.
        track = by_id.get(step["track"]) or by_id.get("settlement")
        if track is None:  # pragma: no cover — settlement is always built
            continue
        existing = track.setdefault("steps", [])
        days = step["expected_duration_days"]
        existing.append({
            "n": len(existing) + 1,
            "key": f"corridor-{step['step_id'].lower()}",
            "title": step["name"].strip('"'),
            "status": "locked",
            "owner": step["responsible_party"],
            "where": None,
            "time": f"{days} days" if days else None,
            "cost": None,
            "depends": ", ".join(step["prerequisite_step_ids"]) or None,
            "line": step["name"].strip('"'),
            "subs": [],
            "blocking": step["blocking"],
            # The "easy to miss" flag + its explanation, carried onto the served step so the
            # roadmap and the plan email can raise it. Empty note for steps without one.
            "nonObvious": bool(step.get("non_obvious")),
            "nonObviousNote": step.get("non_obvious_note") or None,
            "provenance": step["provenance"],
        })


def _flatten_steps(tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten all track steps into a single list (legacy Pathway V2 compatibility)."""
    steps: List[Dict[str, Any]] = []
    for track in tracks:
        for step in track.get("steps", []):
            steps.append(step)
    return steps


def _build_lanes(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build family parallel lanes (Pathway V2 UI format)."""
    draft = case.get("draft", {})
    family = draft.get("familyMembers", {})
    marital = family.get("maritalStatus", "solo")
    has_spouse = marital in ("partner", "partner_kids")
    has_kids = marital in ("partner_kids", "kids_only")

    lanes = []

    if has_spouse:
        spouse = family.get("spouse") or {}
        spouse_name = spouse.get("fullName", "Partner")
        lanes.append({
            "memberKey": "spouse",
            "memberName": spouse_name,
            "memberInitials": _initials(spouse_name),
            "memberLabel": "Partner",
            "step": {
                "title": "Work permit eligibility check",
                "anchorTo": "Visa Step 2",
                "owner": f"You + {_first_name(spouse_name)}",
                "where": "Online",
                "time": "1 week",
                "cost": "—",
                "line": "Dependent spouses may have right to work — confirm with immigration authority.",
                "subs": [
                    "Check dependent work rights",
                    "Confirm via employer HR",
                ],
            },
        })

    if has_kids:
        children = family.get("children") or []
        known_children = (draft.get("knownFamily") or {}).get("children") or []
        all_kids = children if children else known_children

        for i, child in enumerate(all_kids):
            child_name = child.get("fullName", f"Child {i + 1}")
            dob = child.get("dateOfBirth")
            age = _age_from_dob(dob)
            age_label = f", {age}" if age is not None else ""
            basics = draft.get("relocationBasics", {})
            dest_city = basics.get("destCity", "destination")

            lanes.append({
                "memberKey": f"child-{i}",
                "memberName": child_name,
                "memberInitials": _initials(child_name),
                "memberLabel": f"Child{age_label}",
                "step": {
                    "title": f"School enrolment — {dest_city} international",
                    "anchorTo": "Settlement Step 5",
                    "owner": "You",
                    "where": dest_city,
                    "time": "2–4 weeks",
                    "cost": "Variable",
                    "line": f"International school applications open year-round.",
                    "subs": [
                        f"Submit {_first_name(child_name)}'s application online",
                        "Provide previous school records",
                        "Confirm start date with school",
                    ],
                },
            })

    return lanes
