"""Optional housing preference questions → criteria → scoring (PR4).

New OPTIONAL housing questions (commute mode, lifestyle multiselect, temp/permanent
sub-type, preferred/avoid neighbourhoods) populate the already-declared
LivingAreasCriteria fields and the housing-agency sub-type preference. All optional:
a case with none of them still scores on defaults.
"""
from __future__ import annotations

from backend.app.recommendations import criteria_builder as cb
from backend.app.recommendations.plugins.living_areas import (
    LivingAreasCriteria,
    LivingAreasPlugin,
)


def _build(answers):
    return cb.build_criteria_for_assignment(
        assignment_id="a1", case_id="c1", selected_services=["housing"],
        saved_answers=answers, case_context={"destCity": "Oslo", "destCountry": "NO"},
    )


def test_lifestyle_multiselect_becomes_priorities_dict():
    res = _build({"housing_lifestyle": ["safety", "green"]})
    lp = res["living_areas"]["lifestyle_priorities"]
    assert lp["safety"] == 9 and lp["green"] == 9
    assert lp["quiet"] == 5 and lp["nightlife"] == 5


def test_commute_mode_applied_to_commute_work():
    res = _build({"commute_mins": 30, "commute_mode": "bike"})
    assert res["living_areas"]["commute_work"]["mode"] == "bike"


def test_subtype_preference_flows_to_housing_agencies():
    res = _build({"housing_subtype": "temporary"})
    # Fanned out to housing_agencies, which reads it; living_areas ignores it.
    assert res["housing_agencies"]["subtype_preference"] == "temporary"


def test_preferred_and_avoid_areas_shaped_to_lists():
    res = _build({"preferred_areas": "Frogner, Grünerløkka", "avoid_areas": "Sentrum"})
    la = res["living_areas"]
    assert la["preferred_areas"] == ["Frogner", "Grünerløkka"]
    assert la["avoid_areas"] == ["Sentrum"]


def test_no_optional_answers_still_builds_defaults():
    res = _build({})  # nothing optional answered
    la = res["living_areas"]
    assert la["budget_monthly"] == {"min": 2000, "max": 5000}
    assert "lifestyle_priorities" not in la  # defaults handled in the scorer
    assert la.get("preferred_areas", []) == []


def test_scorer_boosts_preferred_and_penalizes_avoid():
    p = LivingAreasPlugin()
    item = {"item_id": "la-o1", "name": "Frogner", "city": "Oslo", "avg_rent_2br": 25000,
            "typical_sqm_range": [70, 100], "tags": {"safety": 8}, "rating": 4.4,
            "availability_level": "high"}
    base = p.score(LivingAreasCriteria(destination_city="Oslo"), item)
    pref = p.score(LivingAreasCriteria(destination_city="Oslo", preferred_areas=["Frogner"]), item)
    avoid = p.score(LivingAreasCriteria(destination_city="Oslo", avoid_areas=["Frogner"]), item)
    assert pref["score_raw"] > base["score_raw"]
    assert avoid["score_raw"] < base["score_raw"]
    # Avoided area is still scored (not filtered to 0 unless already 0).
    assert "avoid" in avoid["rationale"].lower()
