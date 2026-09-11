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
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from ...relopass.corridors import load_corridor
from ...relopass.corridors.feasibility import required_lead_time_days
from ...relopass.corridors.scheduler import schedule_steps
from . import corridor_registry
from . import isd_visa_required
from .nationality_class import EU_EEA, OWN_NATIONAL, classify
from .wizard_draft_mapper import extract_profile_from_wizard_draft

log = logging.getLogger(__name__)

#: Which roadmap track each corridor step belongs in. Track ids mirror
#: ``roadmap_builder``'s own ("visa", "family", "settlement"), so injected steps land beside the
#: generic ones instead of in a parallel structure the UI would have to learn.
_TRACK_BY_STEP: Dict[str, str] = {
    # Not immigration acts, and not in the visa lane. `timeline_service._CORRIDOR_STEP_PHASE`
    # already classifies these two as `pre_departure` and `logistics` respectively, against
    # `immigration` for the permit and visa steps — the same distinction, made by the same
    # corridor data, one layer up. Routing them to "visa" put them in a track that
    # `_visa_track_required` does not build for a free mover, so they were dropped from the
    # plan while still counting toward its duration.
    "JOB_OFFER_CONTRACT": "civil",
    "EMPLOYMENT_PERMIT_APPLICATION": "visa",
    "EMPLOYMENT_PERMIT_GRANTED": "visa",
    "D_VISA_APPLICATION": "visa",
    "D_VISA_GRANTED": "visa",
    "TRAVEL_TO_IE": "settlement",
    "IRP_REGISTRATION": "visa",
    "STAMP4_ELIGIBILITY": "visa",
    "FAMILY_REGISTRATION": "family",
    "PPSN": "settlement",
    "REVENUE_REGISTRATION": "settlement",
    "BANK_ACCOUNT": "settlement",
    "HEALTH_SETUP": "settlement",

    # NO→FR (RETURNING_EEA_CITIZEN) Phase-A — Norwegian exit admin. These are
    # home-country DEPARTURE obligations, not French settlement; without an entry here
    # they fell to the `settlement` default and rendered under "Settlement" (settle in
    # France) rather than "Pre-departure". Their real home is the roadmap's pre-departure
    # track (roadmap_builder._build_predeparture_track), the mirror of the return track.
    "A0_DEPART_NO": "predeparture",
    "A1_FOLKEREGISTER": "predeparture",
    "A2_PRESERVE_BANKID": "predeparture",
    "A3_NO_TAX_RESIDENCE": "predeparture",
    "A4_EXIT_YEAR_RETURN": "predeparture",
    "A5_FOLKETRYGDEN_EXIT": "predeparture",
    "A6_HELFO_EHIC": "predeparture",
    "A7_PRESERVE_PENSION": "predeparture",
    "A8_NOTIFY_NAV": "predeparture",
    "A9_BANKING_UTILITIES": "predeparture",
}

#: Steps that exist only because the mover is a third-country national. An EEA national on this
#: corridor needs no permit, no entry visa and no immigration registration.
#:
#: `FAMILY_REGISTRATION` is here as well as in `_FAMILY_GATED`, and needs both: it is
#: conditioned on the household relocating AND on the third-country path. Its authored title
#: names Stamp 1G, which is a Critical Skills *dependant* permission — an EEA family member
#: neither receives nor needs it, and serving them the step states an entitlement they do not
#: have. Gating on family alone shipped exactly that.
_IMMIGRATION_GATED = frozenset({
    "EMPLOYMENT_PERMIT_APPLICATION", "EMPLOYMENT_PERMIT_GRANTED",
    "D_VISA_APPLICATION", "D_VISA_GRANTED",
    "IRP_REGISTRATION", "STAMP4_ELIGIBILITY",
    "FAMILY_REGISTRATION",
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
    # NO→FR authored exit steps replace the generic pre-departure placeholders they
    # detail, so a mover never sees both "De-register from {home}" and the specific
    # "Report the move to Folkeregisteret" side by side.
    "A1_FOLKEREGISTER": ("predep-deregister",),
    "A4_EXIT_YEAR_RETURN": ("predep-tax",),
    "A5_FOLKETRYGDEN_EXIT": ("predep-social",),
    "A9_BANKING_UTILITIES": ("predep-financial",),
}

#: Exception cases that presuppose the third-country path, and must therefore be withheld from
#: a mover the classifier positively resolves as a free mover — the same rule the step graph
#: already follows, applied to the advisories, which were previously emitted unconditionally.
#:
#: This is a *resolved* answer, not a suppressed one. "Is this nationality visa-required for
#: Ireland?" is an EXTERNAL_LOOKUP we do not hold — but for an EU/EEA or Irish national the
#: answer is no as a matter of free movement, not as a matter of the missing table. Withholding
#: is honest here in a way it would not be for an unclassified nationality, which still fails
#: open and still receives every advisory.
_THIRD_COUNTRY_ONLY_ADVISORIES = frozenset({
    "VISA_REQUIRED_NATIONAL",
    "SPANISH_LTR_DOES_NOT_TRANSFER",
    "FAMILY_REUNIFICATION_CSEP",
})

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


def _resolve_visa_required_advisory(nationality: Optional[str]) -> Optional[str]:
    """The VISA_REQUIRED_NATIONAL advisory, answered — or None to keep the hedge.

    The pathway declares ``visa_required_nationality`` as
    ``EXTERNAL_LOOKUP -> isd_visa_required.{nationality_iso}``, and that lookup now exists
    (`isd_visa_required`, backed by a committed artifact). Where it resolves, the mover gets
    an answer instead of an instruction to go and ask an embassy the question this product
    exists to answer.

    Returns None for a nationality the lookup cannot place, which keeps the existing
    unasserted advisory. That is the whole reason `visa_required` is three-valued: a
    nationality we failed to parse must never be reported as "no visa needed".

    The visa-free answer is deliberately NOT phrased as "you need nothing". Two of Ireland's
    exemptions (an EEA-family residence card, the UK short-stay waiver) can make a
    visa-required person exempt, and the preclearance rule can bind a visa-EXEMPT spouse of a
    Critical Skills holder — so the "no" carries that caveat rather than closing the question.
    """
    required = isd_visa_required.visa_required(nationality)
    if required is None:
        return None

    src = isd_visa_required.source()
    if required:
        carve_outs = "; ".join(
            e["quote"] for e in isd_visa_required.exemptions_not_resolvable_from_nationality()
        )
        return (
            f"Your nationality is visa-required for Ireland: a long-stay 'D' Employment visa "
            f"must be applied for and GRANTED before you travel — the employment permit alone "
            f"does not permit entry. Each visa-required family member needs their own visa. "
            f"Two exemptions do not depend on nationality and we cannot check them for you — "
            f"{carve_outs}. Source: {src['name']}."
        )
    return (
        f"Your nationality is not on Ireland's visa-required list, so no entry visa is needed "
        f"to land. Note that this is separate from PRECLEARANCE: the spouse or partner of a "
        f"Critical Skills Employment Permit holder must apply for preclearance before "
        f"travelling even when visa-exempt (this does not apply to citizens of Switzerland or "
        f"the UK). You must still register your permission after arrival. "
        f"Source: {src['name']}."
    )


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


def _critical_path_days(steps: List[Any]) -> int:
    """Longest path through the retained step graph, in days.

    Delegates to ``scheduler.schedule_steps`` — the same forward topological projection the
    HR feasibility widget and the ``rce.deadlines`` writer already use — rather than adding a
    second, subtly different notion of how long a corridor takes. Steps that run in parallel
    are not double-counted, which is why this is a critical path and not a sum.

    The base date is arbitrary and never leaves this function: we return an interval, so the
    result is independent of the clock and the caller stays deterministic.
    """
    if not steps:
        return 0
    base = date(2000, 1, 1)
    completions = schedule_steps(steps, base)
    if not completions:
        return 0
    return (max(completions.values()) - base).days


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
        retained: List[Any] = []

        for step in agent.step_graph:
            sid = step.step_id
            if sid in _IMMIGRATION_GATED and not is_third_country:
                continue
            if sid in _FAMILY_GATED and not has_family:
                continue
            retained.append(step)

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
                # "action" | "nothing_to_do". The pathway marks STAMP4_ELIGIBILITY as
                # `nothing_to_do`: after 21 months on a Critical Skills permit she moves to
                # Stamp 4 with no renewal to file. It belongs on the roadmap — it is one of
                # the corridor's flagged non-obvious facts, and a good one — but it is not a
                # task, and a task nobody can ever complete nags forever.
                "outcome_type": getattr(step, "outcome_type", "action") or "action",
                # The trap flag AND its plain-language explanation. The loader parses both
                # (loader.py:134,142) but the overlay used to drop them — the exact analogue
                # of the advisories bug #1953 fixed, one layer down. Seven CSEP steps carry
                # them (the emergency-tax 40%, the proof-of-address catch-22, the
                # ordinarily-resident health test), and without this they never reach the
                # roadmap the mover opens.
                "non_obvious": bool(getattr(step, "non_obvious", False)),
                "non_obvious_note": getattr(step, "non_obvious_note", "") or "",
                "provenance": provenance,
            })

        advisories: List[Dict[str, Any]] = []
        for case_ in agent.exception_cases:
            if case_.id in _THIRD_COUNTRY_ONLY_ADVISORIES and not is_third_country:
                continue
            resolved_visa = (
                _resolve_visa_required_advisory(profile.get("nationality"))
                if case_.id == "VISA_REQUIRED_NATIONAL"
                else None
            )
            if resolved_visa is not None:
                # The lookup the pathway declares now exists — answer, do not defer.
                advisories.append({
                    "id": case_.id, "cite": case_.cite, "text": resolved_visa,
                    "asserted": True, "provenance": provenance,
                })
                continue

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
            # Critical path to the arrival anchor, via the function the HR feasibility widget
            # already uses. This replaced a hand-rolled accumulator that summed durations in
            # YAML declaration order and so double-counted parallel branches: on NO_FR it
            # reported 349 pre-arrival days against a 79-day whole journey, which a critical
            # path cannot do. ES_IE is a straight chain, so its 104 is unchanged.
            "pre_arrival_days": required_lead_time_days(retained),
            "total_days": _critical_path_days(retained),
            "provenance": provenance,
            # The WHOLE journey, not the pre-arrival runway. `pre_arrival_days` used to fill
            # this, which read to a mover as "how long my relocation takes" while measuring
            # only the part before the plane. On a free-movement corridor where nothing must
            # happen before travel that produced `totals.time = "1 days"` beside a 21-day
            # step — measured on FR→NO, which carries 255 production cases.
            "time_estimate": _humanise_days(_critical_path_days(retained)),
        }
    except Exception:  # noqa: BLE001 — never break the employee roadmap
        log.warning("corridor_overlay failed; roadmap falls back to generic", exc_info=True)
        return None
