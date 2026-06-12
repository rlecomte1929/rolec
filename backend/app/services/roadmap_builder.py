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
    if _visa_track_required(draft):
        tracks.append(_build_visa_track(case))
    tracks.append(_build_civil_track(case))
    family_track = _build_family_track(case)
    if family_track:
        tracks.append(family_track)
    tracks.append(_build_settlement_track(case))

    # Outcome labels
    outcomes = ["Right to live and work in destination", "Civil registration complete"]
    if has_spouse:
        outcomes.append("Partner registered")
    if has_kids:
        outcomes.append("Children enrolled in school")

    # Time estimate (rough based on destination)
    dest = (basics.get("destCountry") or "").upper()
    time_estimate = "12–16 weeks" if dest in ("US", "AU", "JP", "SG", "CA") else "8–14 weeks"

    # Cost estimate
    cost_estimate = "€600–€900"

    # Employer covers note
    employer = (draft.get("assignmentContext") or {}).get("employerName", "Your employer")

    return {
        "totals": {
            "time": time_estimate,
            "cost": cost_estimate,
            "employerCovers": f"{employer} covers sponsorship and immigration fees",
        },
        "outcomes": outcomes,
        "tracks": tracks,
        # Flat steps list for Pathway V2 compatibility (legacy shape)
        "steps": _flatten_steps(tracks),
        # Family parallel lanes (Pathway V2 shape)
        "lanes": _build_lanes(case),
    }


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
