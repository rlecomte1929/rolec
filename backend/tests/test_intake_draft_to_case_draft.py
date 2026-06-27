"""AIQ-1311 · Unit tests for the snake_case intake draft → camelCase case draft converter.

The backend twin of frontend/src/features/platform-v2/intake/intakeToCaseDraft.ts.
Verifies snake→camel parity (incl. the work/commute fields the TS omits), member
mapping (partner→spouse, child→children), and empty-field drop-out.
"""
from backend.intake_draft_to_case_draft import intake_draft_to_case_draft
from backend.intake_completeness import missing_intake_basics


# The exact flat snake_case shape the wizard autosaves into case_assignments.intake_draft.
FULL_SNAKE = {
    "origin_country": "FR",
    "origin_city": "Paris",
    "dest_country": "NL",
    "dest_city": "Amsterdam",
    "target_date": "2026-09-25",
    "purpose": "Employment",
    "full_name": "Marc Dubois",
    "email": "marc@example.com",
    "nationality": "FR",
    "passport_country": "FR",
    "passport_expiry": "2030-01-01",
    "members": [
        {"kind": "partner", "name": "Sophie Dubois", "needs_work_permit": "yes"},
        {"kind": "child", "dob": "2018-04-02"},
    ],
    "job_title": "Engineer",
    "contract_type": "permanent",
    "contract_start": "2026-10-01",
    "salary_band": "B4",
    "office_address": "Herengracht 1, Amsterdam",
    "work_pattern": "hybrid",
    "commute_mins": 30,
    "commute_mode": ["bike", "train"],
}


def test_relocation_basics_mapped_to_camel():
    out = intake_draft_to_case_draft(FULL_SNAKE)
    rb = out["relocationBasics"]
    assert rb["originCountry"] == "FR"
    assert rb["originCity"] == "Paris"
    assert rb["destCountry"] == "NL"
    assert rb["destCity"] == "Amsterdam"
    assert rb["purpose"] == "Employment"
    assert rb["targetMoveDate"] == "2026-09-25"
    assert rb["hasDependents"] is True


def test_converted_full_draft_passes_validator():
    """The core P0 assertion: a fully-filled snake draft, once converted, is no
    longer 'missing' the relocationBasics the submit validator checks."""
    out = intake_draft_to_case_draft(FULL_SNAKE)
    assert missing_intake_basics(out) == []


def test_employee_and_assignment_context_mapped():
    out = intake_draft_to_case_draft(FULL_SNAKE)
    ep = out["employeeProfile"]
    assert ep["fullName"] == "Marc Dubois"
    assert ep["passportCountry"] == "FR"
    assert ep["email"] == "marc@example.com"
    ac = out["assignmentContext"]
    assert ac["jobTitle"] == "Engineer"
    assert ac["contractStartDate"] == "2026-10-01"
    assert ac["workLocation"] == "Herengracht 1, Amsterdam"


def test_work_and_commute_fields_carried_through():
    """These are omitted by the TS converter; the backend twin must carry them."""
    ac = intake_draft_to_case_draft(FULL_SNAKE)["assignmentContext"]
    assert ac["workPattern"] == "hybrid"
    assert ac["commuteMins"] == 30
    assert ac["commuteMode"] == ["bike", "train"]


def test_members_map_to_spouse_and_children():
    fm = intake_draft_to_case_draft(FULL_SNAKE)["familyMembers"]
    assert fm["spouse"]["fullName"] == "Sophie Dubois"
    assert fm["spouse"]["wantsToWork"] is True
    assert fm["children"] == [{"dateOfBirth": "2018-04-02", "relationship": "child"}]


def test_no_partner_yields_no_spouse_and_no_dependents():
    out = intake_draft_to_case_draft({"origin_country": "FR", "members": []})
    assert out["familyMembers"]["spouse"] is None
    assert out["familyMembers"]["children"] == []
    assert out["relocationBasics"]["hasDependents"] is False


def test_empty_strings_drop_to_none():
    out = intake_draft_to_case_draft({"origin_country": "", "origin_city": "Paris"})
    assert out["relocationBasics"]["originCountry"] is None
    assert out["relocationBasics"]["originCity"] == "Paris"


def test_empty_draft_is_safe():
    out = intake_draft_to_case_draft({})
    assert out["relocationBasics"]["originCountry"] is None
    assert out["familyMembers"]["children"] == []
    # And the validator reports everything missing (so submit still 400s for a blank draft).
    assert missing_intake_basics(out) == [
        "originCountry",
        "originCity",
        "destCountry",
        "destCity",
        "purpose",
        "targetMoveDate",
    ]
