"""Backend port of the wizard's snake_case -> camelCase-nested converter.

This is the server-authoritative bridge that fixes the intake-submit P0
(AIQ-1311): the wizard autosaves a flat snake_case draft to
``case_assignments.intake_draft``, but the submit guard validates the canonical
camelCase ``relocationBasics.*`` shape. Without this conversion a fully-filled
wizard reports step-1 as missing and 400s.

Mirrors ``frontend/src/features/platform-v2/intake/intakeToCaseDraft.ts``.
"""
from backend.intake_completeness import missing_intake_basics
from backend.intake_draft_to_case_draft import intake_draft_to_case_draft


def _complete_snake_draft() -> dict:
    """A draft shaped exactly like the wizard autosave (verified against prod)."""
    return {
        "origin_country": "FR",
        "origin_city": "Paris",
        "dest_country": "NL",
        "dest_city": "Amsterdam",
        "target_date": "2026-09-25",
        "purpose": "Employment",
        "full_name": "Alice Dupont",
        "email": "alice@example.com",
        "nationality": "FR",
        "passport_country": "FR",
        "passport_expiry": "2030-01-01",
        "members": [{"id": "self", "kind": "self"}],
        "has_pets": False,
        "job_title": "Software Engineer",
        "contract_type": "Permanent",
        "contract_start": "2026-09-25",
        "salary_band": "100-150k",
        "office_address": "Amsterdam",
        "work_pattern": "Hybrid",
        "commute_mins": 30,
        "commute_mode": [],
        "consent": True,
    }


def test_complete_snake_draft_satisfies_submit_validator():
    """THE bug contract: a complete wizard draft must pass the submit guard once
    converted. This is exactly what 400'd before AIQ-1311."""
    converted = intake_draft_to_case_draft(_complete_snake_draft())
    assert missing_intake_basics(converted) == []


def test_relocation_basics_keys_are_camel_case():
    converted = intake_draft_to_case_draft(_complete_snake_draft())
    basics = converted["relocationBasics"]
    assert basics["originCountry"] == "FR"
    assert basics["originCity"] == "Paris"
    assert basics["destCountry"] == "NL"
    assert basics["destCity"] == "Amsterdam"
    assert basics["purpose"] == "Employment"
    assert basics["targetMoveDate"] == "2026-09-25"


def test_incomplete_draft_reports_only_missing_basics():
    draft = _complete_snake_draft()
    draft["dest_city"] = ""
    draft["target_date"] = ""
    converted = intake_draft_to_case_draft(draft)
    assert sorted(missing_intake_basics(converted)) == ["destCity", "targetMoveDate"]


def test_employee_profile_and_assignment_context_mapped():
    converted = intake_draft_to_case_draft(_complete_snake_draft())
    assert converted["employeeProfile"]["fullName"] == "Alice Dupont"
    assert converted["employeeProfile"]["passportCountry"] == "FR"
    assert converted["assignmentContext"]["jobTitle"] == "Software Engineer"
    assert converted["assignmentContext"]["workLocation"] == "Amsterdam"


def test_empty_strings_drop_out_so_deep_merge_keeps_existing():
    """Blank fields must be absent (None), never empty strings, so the backend
    deep-merge never overwrites good data with blanks (mirrors the TS converter)."""
    draft = _complete_snake_draft()
    draft["origin_city"] = ""
    converted = intake_draft_to_case_draft(draft)
    assert converted["relocationBasics"].get("originCity") is None


def test_partner_and_children_derived_from_members():
    draft = _complete_snake_draft()
    draft["members"] = [
        {"id": "self", "kind": "self"},
        {"id": "p", "kind": "partner", "name": "Sam Dupont", "needs_work_permit": "yes"},
        {"id": "c1", "kind": "child", "dob": "2018-05-01"},
    ]
    converted = intake_draft_to_case_draft(draft)
    assert converted["relocationBasics"]["hasDependents"] is True
    assert converted["familyMembers"]["spouse"]["fullName"] == "Sam Dupont"
    assert converted["familyMembers"]["spouse"]["wantsToWork"] is True
    assert converted["familyMembers"]["children"] == [
        {"dateOfBirth": "2018-05-01", "relationship": "child"}
    ]


def test_no_dependents_when_only_self():
    converted = intake_draft_to_case_draft(_complete_snake_draft())
    assert converted["relocationBasics"]["hasDependents"] is False


def test_handles_empty_or_missing_draft():
    assert missing_intake_basics(intake_draft_to_case_draft({})) == [
        "originCountry",
        "originCity",
        "destCountry",
        "destCity",
        "purpose",
        "targetMoveDate",
    ]
    # None must not raise.
    intake_draft_to_case_draft(None)
