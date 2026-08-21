"""[AIQ-1867] Bring a corridor's authored step graph into the EMPLOYEE roadmap.

The corridor registry already holds far better journeys than the employee ever sees.
``corridors/ES_IE/pathways/CSEP_2026/v1.yaml`` is a 13-step sequenced Ireland route with real
durations — permit, **long-stay 'D' visa**, IRP registration, PPSN, Revenue, bank, health,
**family registration**, Stamp 4 — plus exception cases whose hints name Venezuela outright.
Its only reader was ``case_feasibility.feasibility_for_case`` → ``hr_case_detail``: an HR
timeline widget. ``roadmap_builder.derive_roadmap`` read no corridor asset at all, so the person
actually moving got a generic two-step visa track, no entry visa, and a family step asserting
dependents "need their own permit" — the opposite of the Critical Skills rule.

This module is the join, mirroring the role ``case_feasibility`` plays for the HR view: the
registry lives in ``app/``, the loader must not import ``app/``, so they meet here.

**Fallback-safe by construction.** Every failure path returns ``None``, and ``None`` means
*render exactly what we rendered before*. An absent overlay must never be shown as reassurance.

**Two honesty rules this module exists to keep.**

*Gate by nationality class, never by country name.* The step graph's permit and visa steps apply
to third-country nationals. An EEA national on the same corridor needs none of them, and
name-matching a country into a permit rule is how that goes wrong.

*Never assert an input we do not hold.* The pathway declares ``visa_required_nationality`` as
``EXTERNAL_LOOKUP -> isd_visa_required.{nationality_iso}``. That lookup does not exist in this
repo. Telling someone "you are a visa-required national" on the strength of a missing table
would be inventing the fact that decides whether she can board a plane, so the advisory is
worded conditionally and points at the register that really holds the answer. Same for
``holds_eu_ltr_in_spain``, which the file marks USER_INPUT and the wizard does not yet ask.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from ...relopass.corridors import load_corridor
from . import corridor_registry
from .nationality_class import EU_EEA, OWN_NATIONAL, classify
from .wizard_draft_mapper import extract_profile_from_wizard_draft

log = logging.getLogger(__name__)

#: Which roadmap track each corridor step belongs in. Track ids mirror
#: ``roadmap_builder``'s own ("visa", "family", "settlement"), so injected steps land beside the
#: generic ones instead of in a parallel structure the UI would have to learn.
_TRACK_BY_STEP: Dict[str, str] = {
    "JOB_OFFER_CONTRACT": "visa",
    "EMPLOYMENT_PERMIT_APPLICATION": "visa",
    "EMPLOYMENT_PERMIT_GRANTED": "visa",
    "D_VISA_APPLICATION": "visa",
    "D_VISA_GRANTED": "visa",
    "TRAVEL_TO_IE": "visa",
    "IRP_REGISTRATION": "visa",
    "STAMP4_ELIGIBILITY": "visa",
    "FAMILY_REGISTRATION": "family",
    "PPSN": "settlement",
    "REVENUE_REGISTRATION": "settlement",
    "BANK_ACCOUNT": "settlement",
    "HEALTH_SETUP": "settlement",
}

#: Steps that exist only because the mover is a third-country national. An EEA national on this
#: corridor needs no permit, no entry visa and no immigration registration.
_IMMIGRATION_GATED = frozenset({
    "EMPLOYMENT_PERMIT_APPLICATION", "EMPLOYMENT_PERMIT_GRANTED",
    "D_VISA_APPLICATION", "D_VISA_GRANTED",
    "IRP_REGISTRATION", "STAMP4_ELIGIBILITY",
})

#: Steps that must be complete before travel. `D_VISA_GRANTED` is the one the corridor file is
#: emphatic about: "The permit alone does not permit entry."
_BLOCKING = frozenset({"D_VISA_GRANTED", "EMPLOYMENT_PERMIT_GRANTED"})

#: Only present when the household is actually relocating.
_FAMILY_GATED = frozenset({"FAMILY_REGISTRATION"})

#: Generic scaffold steps a corridor step replaces outright. Leaving both in place is worse than
#: leaving the generic one alone: the scaffold's `spouse-permit` tells the family they each need
#: "their own permit linked to the primary applicant", which for a Critical Skills move is the
#: opposite of the rule the corridor step states. Two contradictory instructions in one plan is
#: not a richer plan.
_SUPERSEDES: Dict[str, Tuple[str, ...]] = {
    "EMPLOYMENT_PERMIT_APPLICATION": ("permit", "sponsorship"),
    "IRP_REGISTRATION": ("police",),
    "FAMILY_REGISTRATION": ("spouse-permit",),
    "PPSN": ("tax",),
}

#: Exception cases whose condition depends on an input we cannot resolve. Surfaced, never
#: asserted — see the module docstring.
_UNRESOLVABLE_CONDITIONS = {
    "VISA_REQUIRED_NATIONAL": (
        "If your nationality is on Ireland's visa-required list, a long-stay 'D' Employment "
        "visa must be applied for and GRANTED before you travel — the employment permit alone "
        "does not permit entry. Check the current list with Irish Immigration Service Delivery "
        "(irishimmigration.ie) or the Irish embassy for your nationality."
    ),
    "SPANISH_LTR_DOES_NOT_TRANSFER": (
        "If you hold EU long-term residence or a TIE in Spain, note that it confers no entry or "
        "work right in Ireland — Ireland is not bound by Directive 2003/109/EC. The full permit, "
        "visa and registration sequence still applies."
    ),
}


def _has_family_relocating(draft: Dict[str, Any]) -> bool:
    family = draft.get("familyMembers") or {}
    return (family.get("maritalStatus") or "solo") in ("partner", "partner_kids", "kids_only")


def _resolve_pathway(origin: Optional[str], destination: Optional[str]) -> Optional[Tuple[Any, str, str]]:
    """(CorridorAgent, corridor_id, pathway_id) or None. Never raises.

    Resolves from the origin/destination pair exactly as ``case_feasibility`` does, so the
    employee roadmap and the HR feasibility widget can never disagree about which corridor a
    case belongs to.
    """
    if not origin or not destination:
        return None
    corridor_id = corridor_registry.normalize_corridor_id(f"{origin}_{destination}")
    if not corridor_id:
        return None
    pathways = corridor_registry.get_pathways(corridor_id)
    if not pathways:
        return None
    path = corridor_registry.get_pathway_file(corridor_id, pathways[0].id)
    if path is None:
        return None
    return load_corridor(path), corridor_id, pathways[0].id


def _humanise_days(days: int) -> str:
    if days <= 0:
        return "—"
    if days < 14:
        return f"{days} days"
    weeks = round(days / 7)
    return f"~{weeks} weeks"


def corridor_overlay(case: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Corridor-derived steps and advisories for a case, or None to change nothing.

    Returns ``corridor_steps`` (each already assigned a track), ``advisories`` from the
    pathway's exception cases, ``pre_arrival_days`` (the authored critical path up to and
    including travel) and the provenance every injected step must carry.
    """
    try:
        draft = (case or {}).get("draft") or {}
        basics = draft.get("relocationBasics") or {}
        origin = basics.get("originCountry") or basics.get("origin_country")
        destination = basics.get("destCountry") or basics.get("dest_country")

        resolved = _resolve_pathway(origin, destination)
        if resolved is None:
            return None
        agent, corridor_id, pathway_id = resolved

        profile = extract_profile_from_wizard_draft(draft)
        nat_class = classify(profile.get("nationality"), destination)
        # FAIL OPEN, deliberately. `classify` resolves ISO codes and EU/EEA country NAMES, but
        # not third-country names: classify("Venezuela", "IE") is None, not THIRD_COUNTRY, and
        # 426 of 1389 wizard cases store a country name rather than an ISO code. Dropping the
        # permit and visa steps on an unresolved nationality would show a visa-required national
        # no visa at all — the most expensive possible wrong answer. So we only withhold them
        # from someone we positively know is a free mover. Same stance as
        # `roadmap_builder._visa_track_required`, which keeps the visa track on "unknown".
        is_third_country = nat_class not in (EU_EEA, OWN_NATIONAL)
        has_family = _has_family_relocating(draft)

        provenance = {
            "corridor": corridor_id,
            "pathway": pathway_id,
            # corridors/<id>/corridor.yaml states in its own header that these figures are
            # indicative and NOT SME-verified. That must survive all the way to the UI.
            "verification": "representative",
        }

        steps: List[Dict[str, Any]] = []
        pre_arrival_days = 0
        seen_travel = False

        for step in agent.step_graph:
            sid = step.step_id
            if sid in _IMMIGRATION_GATED and not is_third_country:
                continue
            if sid in _FAMILY_GATED and not has_family:
                continue

            if not seen_travel:
                pre_arrival_days += int(step.expected_duration_days or 0)
                if sid.startswith("TRAVEL_"):
                    seen_travel = True

            steps.append({
                "step_id": sid,
                "track": _TRACK_BY_STEP.get(sid, "settlement"),
                "name": step.name,
                "responsible_party": step.responsible_party,
                "expected_duration_days": int(step.expected_duration_days or 0),
                "prerequisite_step_ids": list(step.prerequisite_step_ids or ()),
                "blocking": sid in _BLOCKING,
                # The pathway's own pivot between "before the move" and "after landing".
                # Exactly one step per corridor carries it (the TRAVEL_* step), which lets a
                # consumer place every step by POSITION instead of knowing its name — see
                # timeline_service._corridor_milestones.
                "arrival_anchor": bool(getattr(step, "arrival_anchor", False)),
                "provenance": provenance,
            })

        advisories: List[Dict[str, Any]] = []
        for case_ in agent.exception_cases:
            text = _UNRESOLVABLE_CONDITIONS.get(case_.id)
            if text is not None:
                # Input we do not hold: surface it, worded as a condition she can check.
                advisories.append({
                    "id": case_.id, "cite": case_.cite, "text": text,
                    "asserted": False, "provenance": provenance,
                })
            elif case_.id == "FAMILY_REUNIFICATION_CSEP" and has_family:
                # This one we CAN resolve — the household is in the draft.
                advisories.append({
                    "id": case_.id, "cite": case_.cite,
                    "text": (case_.hint or "").strip(),
                    "asserted": True, "provenance": provenance,
                })

        if not steps:
            return None

        superseded = tuple(
            key
            for s in steps
            for key in _SUPERSEDES.get(s["step_id"], ())
        )

        return {
            "corridor_steps": steps,
            "superseded_generic_keys": superseded,
            "advisories": advisories,
            "pre_arrival_days": pre_arrival_days,
            "provenance": provenance,
            "time_estimate": _humanise_days(pre_arrival_days),
        }
    except Exception:  # noqa: BLE001 — never break the employee roadmap
        log.warning("corridor_overlay failed; roadmap falls back to generic", exc_info=True)
        return None
