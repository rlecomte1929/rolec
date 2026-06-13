"""
AIQ-973 (ASK-ONCE) — intake fields the user already gave must be surfaced as
pre-filled 'confirm' values in the immigration interview, never re-asked as blank
required questions.

Two layers:
  1. The pure mapper `_map_intake_to_vault_fields` resolves intake_data → the
     interview's vault_field names (across wizard/orchestrator key shapes).
  2. With that map overlaid as the interview `vault`, `get_next_question` returns
     the known fields as pre_filled (never blank+required), while genuinely
     net-new fields (passport issue date, 2nd nationality) are still asked.
"""
from backend.app.services.immigration_service import _map_intake_to_vault_fields
from backend.app.services.immigration_interview_engine import get_next_question, load_questions

# The 5 fields the provenance audit found re-asked 4–5x — plus the spouse trio.
KNOWN_FIELDS = {
    "legal_first_name", "legal_last_name", "date_of_birth", "nationality",
    "passport_number", "passport_expiry",
    "spouse_name", "spouse_dob", "spouse_nationality",
}
# Fields NOT in intake — must still be asked fresh.
NET_NEW_FIELDS = {"passport_issue_date", "second_nationality", "place_of_birth", "passport_country"}


def _wizard_intake() -> dict:
    return {
        "primaryApplicant": {
            "fullName": "Marie Claire Dubois", "dateOfBirth": "1990-03-12",
            "nationality": "FR", "passportNumber": "X1234567", "passportExpiry": "2030-01-01",
        },
        "familyMembers": {"spouse": {"fullName": "Jean Dubois", "dateOfBirth": "1988-07-04", "nationality": "FR"}},
    }


# ── Layer 1: the pure mapper ────────────────────────────────────────────────

def test_mapper_resolves_wizard_intake():
    r = _map_intake_to_vault_fields(_wizard_intake())
    assert r["legal_first_name"] == "Marie" and r["legal_last_name"] == "Claire Dubois"
    assert r["date_of_birth"] == "1990-03-12" and r["nationality"] == "FR"
    assert r["passport_number"] == "X1234567" and r["passport_expiry"] == "2030-01-01"
    assert r["spouse_name"] == "Jean Dubois" and r["spouse_dob"] == "1988-07-04"
    assert r["spouse_nationality"] == "FR"


def test_mapper_resolves_snake_case_profile_subkey():
    r = _map_intake_to_vault_fields({
        "profile": {"full_name": "Sam Lee", "date_of_birth": "1985-01-01",
                    "nationality": "US", "passport_number": "P9", "passport_expiry": "2029-09-09"},
    })
    assert r["legal_first_name"] == "Sam" and r["legal_last_name"] == "Lee"
    assert r["nationality"] == "US" and r["passport_number"] == "P9"


def test_mapper_never_invents_net_new_fields():
    r = _map_intake_to_vault_fields(_wizard_intake())
    assert NET_NEW_FIELDS.isdisjoint(r.keys())


def test_mapper_empty_and_bad_input():
    assert _map_intake_to_vault_fields({}) == {}
    assert _map_intake_to_vault_fields(None) == {}  # type: ignore[arg-type]


# ── Layer 2: the interview never emits a known field as blank+required ──────

def test_interview_does_not_reask_known_intake_fields():
    questions = load_questions()
    vault = _map_intake_to_vault_fields(_wizard_intake())  # the read-time overlay
    assert vault, "mapper produced no canonical fields"

    answers: dict = {"q_marital_status": "married"}  # surface the conditional spouse Qs
    confirmed: list = []
    seen_prefilled: set = set()
    seen_blank_required_netnew = False

    for _ in range(60):  # bounded walk
        q = get_next_question(answers, vault, confirmed, questions)
        if q is None:
            break
        vf = q.get("vault_field") or _vault_field_for(q["question_id"], questions)
        if vf in KNOWN_FIELDS:
            # The whole point: a field already in intake must arrive pre-filled,
            # NEVER as a blank required input.
            assert q["pre_filled"] is True and q.get("existing_value") not in (None, ""), (
                f"{vf} was re-asked as blank (pre_filled={q['pre_filled']})"
            )
            seen_prefilled.add(vf)
            confirmed.append(vf)  # user confirms → advance
        else:
            if q.get("required") and not q.get("pre_filled"):
                if vf in NET_NEW_FIELDS:
                    seen_blank_required_netnew = True
            # answer it to advance (answer keyed by question_id)
            answers[q["question_id"]] = "x"

    # All 5 core fields were surfaced pre-filled (not re-asked).
    core = {"legal_first_name", "date_of_birth", "nationality", "passport_number", "passport_expiry"}
    assert core.issubset(seen_prefilled), f"core fields not pre-filled: {core - seen_prefilled}"
    # And a genuinely net-new field was still asked fresh (control).
    assert seen_blank_required_netnew, "expected at least one net-new field still asked blank"


def _vault_field_for(question_id: str, questions) -> str:
    for q in questions:
        if q.id == question_id:
            return q.vault_field or ""
    return ""
