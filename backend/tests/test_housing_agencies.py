"""Housing agencies — the gated, RFQ-backed housing supplier concept.

Neighbourhoods (living_areas) are advisory content; housing AGENCIES are real
suppliers surfaced from the registry and HR-gated like movers. "Housing" now fans
out to BOTH surfaces. Temp/permanent is a soft sub-type boost, never a hard filter.
"""
from __future__ import annotations

from backend.app.recommendations import criteria_builder as cb
from backend.app.recommendations.registry import get_plugin
from backend.app.recommendations.plugins.base import BasePlugin
from backend.app.recommendations.plugins.housing_agencies import (
    HousingAgenciesCriteria,
    HousingAgenciesPlugin,
    TEMPORARY_TAG,
    PERMANENT_TAG,
)


def _agency(item_id, tag, rating=4.5):
    return {"item_id": item_id, "name": item_id, "rating": rating,
            "availability_level": "high", "specialization_tags": [tag]}


def test_housing_agencies_is_a_valid_supplier_category():
    # The seed creates agencies via create_supplier -> validate_supplier_create; if
    # "housing_agencies" isn't a valid service_category the whole seed raises and is
    # silently swallowed (agencies never appear). This pins the category as valid AND
    # validates the exact capability shape seed_housing_agencies builds.
    from backend.app.services.supplier_validation import (
        VALID_SERVICE_CATEGORIES,
        validate_supplier_create,
    )

    assert "housing_agencies" in VALID_SERVICE_CATEGORIES
    ok, err = validate_supplier_create({
        "id": "ha-osl-p1",
        "name": "Frogner Rental Partners",
        "status": "active",
        "capabilities": [{
            "service_category": "housing_agencies",
            "coverage_scope_type": "city",
            "city_name": "Oslo",
            "country_code": "NO",
            "specialization_tags": [PERMANENT_TAG],
            "corporate_clients": True,
            "platform_vetting_status": "approved",
        }],
    })
    assert ok, err


def test_plugin_registered_and_is_gated():
    p = get_plugin("housing_agencies")
    assert isinstance(p, HousingAgenciesPlugin)
    # Agencies are HR-gated + registry-backed (NOT advisory) — unlike neighbourhoods.
    assert p.advisory is False
    assert BasePlugin.advisory is False


def test_housing_fans_out_to_neighbourhoods_and_agencies():
    res = cb.build_criteria_for_assignment(
        assignment_id="a1", case_id="c1", selected_services=["housing"],
        saved_answers={"budget_min": 2000, "budget_max": 5000},
        case_context={"destCity": "Oslo", "destCountry": "NO"},
    )
    assert set(res.keys()) == {"living_areas", "housing_agencies"}
    # Both carry the shared destination/budget shaping.
    assert res["housing_agencies"]["destination_city"] == "Oslo"


def test_backends_for_service_helper():
    assert cb.backends_for_service("housing") == ["living_areas", "housing_agencies"]
    assert cb.backends_for_service("movers") == ["movers"]
    assert cb.backends_for_service("unknown") == []


def test_registry_agencies_are_advisory_free_and_load_empty_static():
    # Registry-only: no static dataset file to rank from.
    assert HousingAgenciesPlugin().load_dataset() == []


def test_subtype_preference_is_a_soft_boost_not_a_filter():
    p = HousingAgenciesPlugin()
    crit = HousingAgenciesCriteria(destination_city="Oslo", subtype_preference="temporary")
    temp = p.score(crit, _agency("t1", TEMPORARY_TAG))
    perm = p.score(crit, _agency("p1", PERMANENT_TAG))
    # Preferred sub-type ranks higher...
    assert temp["score_raw"] > perm["score_raw"]
    # ...but the non-preferred sub-type is NEVER filtered out (still scores > 0).
    assert perm["score_raw"] > 0
    assert temp["metadata"]["housing_subtype"] == "temporary"
    assert perm["metadata"]["housing_subtype"] == "permanent"


def test_no_preference_scores_both_subtypes_equally():
    p = HousingAgenciesPlugin()
    crit = HousingAgenciesCriteria(destination_city="Oslo")  # no subtype preference
    temp = p.score(crit, _agency("t1", TEMPORARY_TAG, rating=4.5))
    perm = p.score(crit, _agency("p1", PERMANENT_TAG, rating=4.5))
    assert temp["score_raw"] == perm["score_raw"]
