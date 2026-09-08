"""Household facts from intake must drive services + RFQ, not plugin defaults."""
from datetime import date

from backend.app.services.household_from_draft import household_from_draft, marital_status
from backend.app.services.question_engine import generate_questions
from backend.app.services.rfq_brief import build_requirements_for_service, draft_supplier_message


def test_household_counts_partner_and_two_children():
    draft = {
        "familyMembers": {
            "maritalStatus": "partner_kids",
            "spouse": {"fullName": "Andre"},
            "children": [
                {"fullName": "Bob1", "dateOfBirth": "2020-01-01"},
                {"fullName": "Bob2", "dateOfBirth": "2010-01-01"},
            ],
        },
        "assignmentContext": {"commuteMins": 30},
    }
    h = household_from_draft(draft)
    assert h["has_partner"] is True
    assert h["child_count"] == 2
    assert h["household_size"] == 4
    assert h["commute_mins"] == 30
    assert h["dependents_ages"]


def test_marital_status_helper():
    assert marital_status(True, 2) == "partner_kids"
    assert marital_status(True, 0) == "partner"
    assert marital_status(False, 1) == "kids_only"
    assert marital_status(False, 0) == "solo"


def test_schools_question_omitted_when_intake_has_ages():
    qs = generate_questions(
        ["schools"],
        case_context={"dependents_ages": "6,16", "destCity": "Dublin"},
        saved_answers={},
    )
    keys = {q["question_key"] for q in qs}
    assert "child_ages" not in keys


def test_people_and_commute_omitted_when_known():
    qs = generate_questions(
        ["movers", "housing"],
        case_context={
            "household_size": 4,
            "commute_mins": 30,
            "originCity": "Madrid",
            "destCity": "Dublin",
        },
        saved_answers={},
    )
    keys = {q["question_key"] for q in qs}
    assert "people" not in keys
    assert "commute_mins" not in keys
    assert "origin_city" not in keys


def test_housing_budget_omitted_when_policy_cap_present():
    qs = generate_questions(
        ["housing"],
        case_context={"housing_cap_amount": 3000, "destCity": "Dublin"},
        saved_answers={},
    )
    keys = {q["question_key"] for q in qs}
    assert "budget_min" not in keys
    assert "budget_max" not in keys


def test_rfq_schools_brief_uses_intake_ages_not_default_eight():
    draft = {
        "relocationBasics": {
            "originCity": "Madrid", "originCountry": "ES",
            "destCity": "Dublin", "destCountry": "IE",
            "targetMoveDate": "2026-10-01",
        },
        "familyMembers": {
            "spouse": {"fullName": "Andre"},
            "children": [
                {"dateOfBirth": "2020-01-01"},
                {"dateOfBirth": "2010-01-01"},
            ],
        },
    }
    req = build_requirements_for_service("schools", {"host_city": "Dublin", "host_country": "IE"}, {}, draft)
    assert req["child_ages"]
    assert req["child_ages"] != "8"


def test_draft_message_summarises_route_and_household():
    msg = draft_supplier_message(
        case={"home_city": "Madrid", "home_country": "ES", "host_city": "Dublin", "host_country": "IE",
              "target_start_date": date(2026, 10, 1)},
        draft={"familyMembers": {"spouse": {"fullName": "A"}, "children": [{"dateOfBirth": "2020-01-01"}]}},
        service_keys=["living_areas", "movers", "schools"],
    )
    assert "Madrid" in msg
    assert "Dublin" in msg
    assert "housing" in msg.lower()
    assert "school" in msg.lower()
    assert "itemised" in msg.lower()
    # No child given names in the supplier-facing draft.
    assert "Bob" not in msg
