"""[AIQ-1867] The corridor's authored step graph must reach the employee, not just HR.

`corridors/ES_IE/pathways/CSEP_2026/v1.yaml` holds a 13-step sequenced Ireland journey with
durations — including `D_VISA_APPLICATION` (40d) and `FAMILY_REGISTRATION` (21d) — and exception
cases whose hints name Venezuela by name. Until now the only reader was
`case_feasibility.feasibility_for_case` → `hr_case_detail`, an HR timeline widget. The employee
roadmap (`roadmap_builder.derive_roadmap`) read no corridor asset at all and emitted a generic
two-step visa track plus a family step asserting dependents "need their own permit" — which is
the opposite of the Critical Skills rule.

Measured against the real case this is for: a Venezuelan national moving Madrid → Dublin with a
family of four. Her true pre-arrival critical path is 104 days; the generic estimate for that
destination was "8-14 weeks", which understates it.

What these tests pin:

  * the corridor steps reach the employee, in the right tracks, with real durations;
  * the entry visa is ordered before travel and is blocking — the permit alone does not admit her;
  * gating is by nationality CLASS, never by country name-match (the EEA permit-gating invariant);
  * an advisory whose input we do not hold is worded conditionally and never asserted;
  * every injected step carries its citation and its REPRESENTATIVE status, because the corridor
    file says in its own header that its figures are not SME-verified;
  * a corridor with no pathway file behaves exactly as it does today.
"""
from __future__ import annotations

from typing import Any, Dict

import backend.app.services.roadmap_corridor_overlay as overlay
from backend.app.services.roadmap_builder import derive_roadmap


def _case(nationality: str = "Venezuela", *, dest: str = "IE", origin: str = "ES",
          marital: str = "partner_kids") -> Dict[str, Any]:
    """A case shaped like Andrea's: VE national, Madrid -> Dublin, family of four."""
    return {
        "id": "case-andrea",
        "status": "open",
        "draft": {
            "relocationBasics": {"originCountry": origin, "destCountry": dest},
            "employeeProfile": {"nationality": nationality, "fullName": "Andrea Test"},
            "assignmentContext": {"employerName": "Google"},
            "familyMembers": {
                "maritalStatus": marital,
                "spouse": {"fullName": "Partner Test"},
                "children": [{"fullName": "Child One"}, {"fullName": "Child Two"}],
            },
        },
    }


def _steps(roadmap: Dict[str, Any]) -> list:
    return roadmap.get("steps", [])


def _keys(roadmap: Dict[str, Any]) -> list:
    return [s.get("key") for s in _steps(roadmap)]


# ── the overlay resolves the corridor ────────────────────────────────────────────────

def test_the_es_ie_pathway_resolves_and_carries_its_durations():
    ov = overlay.corridor_overlay(_case())
    assert ov is not None, "ES_IE declares a CSEP_2026 pathway; it must resolve"

    by_id = {s["step_id"]: s for s in ov["corridor_steps"]}
    assert "D_VISA_APPLICATION" in by_id
    assert "FAMILY_REGISTRATION" in by_id
    # Durations come from the file, not from a guess.
    assert by_id["D_VISA_APPLICATION"]["expected_duration_days"] == 40
    assert by_id["FAMILY_REGISTRATION"]["expected_duration_days"] == 21


def test_an_unknown_corridor_yields_no_overlay():
    """No pathway -> the roadmap must be exactly what it is today."""
    assert overlay.corridor_overlay(_case(dest="ZZ", origin="XX")) is None


def test_the_overlay_never_raises_on_a_malformed_case():
    """Mirrors case_feasibility's discipline: an absent assessment is never reassurance."""
    assert overlay.corridor_overlay({}) is None
    assert overlay.corridor_overlay({"draft": {"relocationBasics": None}}) is None


# ── the entry visa, which appears nowhere today ──────────────────────────────────────

def test_a_third_country_national_gets_the_d_visa_before_travel():
    """The permit alone does not admit her. Ordering is the whole point of the step."""
    roadmap = derive_roadmap(_case("Venezuela"))
    keys = _keys(roadmap)

    assert "corridor-d_visa_application" in keys
    assert "corridor-travel_to_ie" in keys
    assert keys.index("corridor-d_visa_application") < keys.index("corridor-travel_to_ie")


def test_the_visa_grant_is_blocking_not_a_warning():
    """Every requirement_item for Ireland is severity WARN, so nothing marks a critical path."""
    roadmap = derive_roadmap(_case("Venezuela"))
    grant = next(s for s in _steps(roadmap) if s["key"] == "corridor-d_visa_granted")
    assert grant.get("blocking") is True


def test_an_eu_national_on_the_same_corridor_gets_no_visa_steps():
    """Categorise by nationality class, never name-match a country into a permit rule."""
    roadmap = derive_roadmap(_case("Spain"))
    keys = _keys(roadmap)
    assert not [k for k in keys if k and k.startswith("corridor-d_visa")]
    assert not [k for k in keys if k and "employment_permit" in k]


# ── family: the generic copy was actively wrong for Ireland ──────────────────────────

def test_the_family_step_states_the_stamp_1g_rule_not_the_generic_permit_claim():
    """CSEP spouses reside on Stamp 1G and may work WITHOUT a separate permit.

    The generic family track asserted dependents "need their own permit linked to the primary
    applicant", which for this corridor is the opposite of the rule.
    """
    roadmap = derive_roadmap(_case("Venezuela", marital="partner_kids"))
    fam = next(s for s in _steps(roadmap) if s["key"] == "corridor-family_registration")
    assert "1G" in fam["line"] or "1G" in " ".join(fam.get("subs", []))


def test_a_solo_move_gets_no_family_step():
    roadmap = derive_roadmap(_case("Venezuela", marital="solo"))
    assert "corridor-family_registration" not in _keys(roadmap)


# ── honesty about what we do not know ────────────────────────────────────────────────

def _visa_advisory(nationality: str):
    ov = overlay.corridor_overlay(_case(nationality))
    return next(a for a in ov["advisories"] if a["id"] == "VISA_REQUIRED_NATIONAL")


def test_the_visa_advisory_is_now_answered_for_a_visa_required_national():
    """`visa_required_nationality` is EXTERNAL_LOOKUP -> isd_visa_required.{iso}, and the
    lookup now EXISTS.

    This test previously pinned the opposite — that the advisory stays conditional "because we
    hold no ISD list". That premise is gone, and its wording was the product telling Andrea to
    go and ask an embassy the one question the corridor is built to answer.
    """
    adv = _visa_advisory("Venezuela")

    assert adv["asserted"] is True
    assert adv["cite"] == "IE_D_VISA"
    assert "visa-required" in adv["text"].lower()
    assert "granted before you travel" in adv["text"].lower()


def test_the_spouse_nationality_resolves_too():
    """Andrea's spouse is Macedonian. Unresolved, the family's entry route was unstatable."""
    assert _visa_advisory("North Macedonia")["asserted"] is True
    assert "visa-required" in _visa_advisory("MK")["text"].lower()


def test_a_visa_exempt_national_is_told_about_preclearance_not_just_no():
    """The dangerous half of a "no". A CSEP holder's US spouse who reads "no visa needed" and
    books a flight still needs preclearance — a rule no requirement_item carries (0 of 42)."""
    adv = _visa_advisory("United States")

    assert adv["asserted"] is True
    assert "preclearance" in adv["text"].lower()
    assert "not on ireland's visa-required list" in adv["text"].lower()


def test_an_unresolvable_nationality_keeps_the_conditional_wording():
    """The reason `visa_required` is three-valued. A nationality we cannot parse must never
    be reported as "no visa needed" — production holds 'f', 'asdas' and '1212' in this field."""
    adv = _visa_advisory("asdas")

    assert adv["asserted"] is False
    lowered = adv["text"].lower()
    assert "if" in lowered or "check" in lowered


def test_the_visa_advisory_names_the_exemptions_it_cannot_check():
    """A Venezuelan in Spain with a FRENCH spouse is visa-exempt; with a Macedonian or Spanish
    spouse she is not. We cannot tell from a nationality, so the advisory must say so rather
    than assert an unqualified 'you need a visa'."""
    text = _visa_advisory("Venezuela")["text"].lower()

    assert "residence card issued by an eea country" in text
    assert "do not depend on nationality" in text


def test_every_corridor_step_carries_its_citation_and_representative_status():
    """corridors/ES_IE/corridor.yaml: 'REPRESENTATIVE / AUTHORING - NOT SME-verified'.

    A 40-day visa estimate a real family plans around must not render as established fact.
    """
    roadmap = derive_roadmap(_case("Venezuela"))
    injected = [s for s in _steps(roadmap) if str(s.get("key", "")).startswith("corridor-")]
    assert injected

    for step in injected:
        prov = step.get("provenance")
        assert prov, f"{step['key']} has no provenance"
        assert prov["corridor"] == "ES_IE"
        assert prov["pathway"] == "CSEP_2026"
        assert prov["verification"] == "representative"


# ── the timeline she would actually plan around ──────────────────────────────────────

def test_the_authored_critical_path_replaces_the_destination_guess():
    """Generic estimate for IE was '8-14 weeks'. The authored graph beats a country guess.

    `totals.time` used to carry ``pre_arrival_days`` — the runway up to the plane, not the
    journey. Nothing labels it that way: the plan email renders it under a bare "Overview:"
    beside cost, so a mover reads it as how long their relocation takes. On a free-movement
    corridor, where by definition nothing must happen before travel, that shipped
    ``totals.time = "1 days"`` on FR→NO (255 production cases) next to a 21-day step.

    It is now the critical path through the whole retained graph. Both numbers remain
    available; only the one that was mislabelled changed.
    """
    ov = overlay.corridor_overlay(_case("Venezuela"))
    # Unchanged, and still the figure corridors/ES_IE/corridor.yaml derives its
    # at_risk_window_days from.
    assert ov["pre_arrival_days"] == 104
    # The whole journey: 104 to arrival, then IRP (21) and family registration (21).
    assert ov["total_days"] == 146

    roadmap = derive_roadmap(_case("Venezuela"))
    assert roadmap["totals"]["time"] == "~21 weeks"
    assert roadmap["totals"]["time"] != "8–14 weeks"


def test_the_headline_duration_is_never_shorter_than_a_step_inside_it():
    """The arithmetic invariant the '1 days' regression violated.

    Asserts nothing about immigration law, so it cannot rot when the law moves — it only
    says a plan may not claim to be shorter than one of its own steps.
    """
    for nationality in ("Venezuela", "Spain"):
        ov = overlay.corridor_overlay(_case(nationality))
        longest = max(s["expected_duration_days"] for s in ov["corridor_steps"])
        assert ov["total_days"] >= longest


def test_pre_arrival_never_exceeds_the_whole_journey():
    """A critical path to arrival cannot be longer than the critical path through everything.

    The hand-rolled accumulator this replaced summed durations in YAML declaration order,
    double-counting parallel branches: NO_FR reported 349 pre-arrival days against a 79-day
    journey.
    """
    for nationality, origin, dest in (
        ("Venezuela", "ES", "IE"), ("Spain", "ES", "IE"),
        ("France", "FR", "NO"), ("Norway", "NO", "FR"),
    ):
        ov = overlay.corridor_overlay(_case(nationality, origin=origin, dest=dest))
        if ov is None:
            continue
        assert ov["pre_arrival_days"] <= ov["total_days"], f"{origin}_{dest}/{nationality}"


def test_an_unresolvable_nationality_keeps_the_visa_steps():
    """Fail OPEN. This is the case the whole feature exists for and it nearly broke.

    `nationality_class.classify` resolves ISO codes and EU/EEA country NAMES, but not
    third-country names — classify("Venezuela", "IE") returns None, not THIRD_COUNTRY. Measured
    on prod: 426 of 1389 wizard cases store a country name rather than an ISO code. Withholding
    the permit and visa steps on an unresolved nationality would show a visa-required national no
    visa at all, which is the most expensive possible wrong answer.
    """
    for nationality in ("Venezuela", "Venezuelan", "", None, "Freedonia"):
        roadmap = derive_roadmap(_case(nationality))
        keys = _keys(roadmap)
        assert "corridor-d_visa_application" in keys, f"visa steps dropped for {nationality!r}"


def test_a_known_free_mover_is_the_only_one_who_loses_them():
    """The mirror of the above: withhold only from someone we positively know is a free mover."""
    for nationality in ("ES", "Spain", "Spanish", "IE", "Ireland"):
        keys = _keys(derive_roadmap(_case(nationality)))
        assert "corridor-d_visa_application" not in keys, f"visa steps kept for {nationality!r}"


def test_the_corridor_step_replaces_the_wrong_generic_one_rather_than_sitting_beside_it():
    """A plan must not contain both instructions.

    The generic family step says each dependent "need their own permit linked to the primary
    applicant". The corridor step says the CSEP spouse may work on Stamp 1G WITHOUT a separate
    permit. Shipping both to a real family is worse than shipping only the wrong one, because
    now they cannot tell which to act on.
    """
    roadmap = derive_roadmap(_case("Venezuela", marital="partner_kids"))
    keys = _keys(roadmap)

    assert "corridor-family_registration" in keys
    assert "spouse-permit" not in keys, "the contradicting generic step is still present"
    # Same for the permit and the on-arrival registration the corridor states precisely.
    assert "permit" not in keys and "sponsorship" not in keys
    assert "police" not in keys


def test_a_corridor_without_an_overlay_keeps_every_generic_step():
    """Suppression is driven by what the corridor actually supplies, never blanket."""
    keys = _keys(derive_roadmap(_case("Venezuela", origin="XX", dest="ZZ")))
    assert "spouse-permit" in keys
    assert "permit" in keys
