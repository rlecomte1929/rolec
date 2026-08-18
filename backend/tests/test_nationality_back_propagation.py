"""[AIQ-1880] Nationality captured on the immigration profile must reach the requirements gate.

`rules_engine.py:121` reads the case's nationality from exactly one place:

    wizard_cases.draft_json -> employeeProfile.nationality

Nothing writes it. Passport OCR extracts `nationality`, the employee confirms it through
`PUT /employee/cases/{id}/profile`, and it lands in `imm_employee_profiles.nationality` —
a different table that the gate never reads. So the gate's only input stays null and
`classify()` returns None.

Measured in production 2026-08-18: 936 of 1,524 `relocation_cases` have no nationality;
**60** of those have a destination, meaning they are actively served destination
requirements with nothing to gate on. Case 6ecadafe-0fdb-43c5-b8dc-0284e323cf51 (Andrea,
ES->IE) is one of them. She is Venezuelan, so THIRD_COUNTRY is correct for her — but she
receives it by accident, because `effective_class = nationality_class or THIRD_COUNTRY`
fail-safes to exactly the answer she happens to need. Change her destination, or her
nationality, and the accident stops being correct.

These tests pin the chain end-to-end: write nationality -> the gate sees it -> the served
set changes. The FRANCE-shaped fixture is deliberate: Ireland's items are 100%
THIRD_COUNTRY, so an Ireland fixture cannot tell "the gate fired" from "the gate did
nothing". France has both tracks, so only a working gate produces the EU_EEA answer.
"""
from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app import models

CASE = "6ecadafe-0fdb-43c5-b8dc-0284e323cf51"
EMPTY_DRAFT = '{"relocationBasics": {}, "employeeProfile": {}, "familyMembers": {}, "assignmentContext": {}}'

ROUTER = Path(__file__).resolve().parents[1] / "app" / "routers" / "immigration_intake_profile.py"


def _requirement(i: int, scope: str, title: str) -> models.RequirementItem:
    return models.RequirementItem(
        id=f"fr-req-{i}",
        country_code="FRANCE",
        purpose="employment",
        pillar="RESIDENCE",
        title=title,
        description="…",
        severity="WARN",
        owner="EMPLOYEE",
        required_fields_json="[]",
        citations_json="[]",
        applies_to_nationality_classes_json=scope,
        verification_status="representative",
        review_status="approved",
        last_verified_at=datetime.utcnow(),
    )


@pytest.fixture()
def session(monkeypatch):
    engine = create_engine("sqlite://", future=True)
    models.Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE relocation_cases ("
                " id TEXT PRIMARY KEY,"
                " origin_country_code TEXT,"
                " dest_country_code TEXT)"
            )
        )
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr("backend.app.services.requirements_builder.SessionLocal", Session)
    with Session() as s:
        yield s


def _seed(session, *, draft=EMPTY_DRAFT, wizard_dest="FR"):
    """A France-bound case with both a third-country and an EU/EEA requirement."""
    session.add(models.Case(id=CASE, draft_json=draft, dest_country=wizard_dest, purpose="employment"))
    session.add(_requirement(1, '["THIRD_COUNTRY"]', "Long-stay work visa (VLS-TS)"))
    session.add(_requirement(2, '["OWN_NATIONAL", "EU_EEA"]', "EU/EEA worker right of residence"))
    session.add(_requirement(3, None, "Signed employment contract"))  # universal
    session.execute(
        text(
            "INSERT INTO relocation_cases (id, origin_country_code, dest_country_code)"
            " VALUES (:id, 'NO', 'FR')"
        ),
        {"id": CASE},
    )
    session.commit()


def _nationality_in_draft(session) -> str | None:
    case = session.query(models.Case).filter(models.Case.id == CASE).first()
    return (json.loads(case.draft_json).get("employeeProfile") or {}).get("nationality")


# ---------------------------------------------------------------------------
# The chain: written nationality must change what the gate serves.
# ---------------------------------------------------------------------------


def test_synced_nationality_reaches_the_gate_and_changes_the_served_set(session):
    """THE test. Before the sync the gate is blind; after it, the EU track is served."""
    from backend.app.services.nationality_sync import sync_nationality_to_case
    from backend.app.services.requirements_builder import compute_case_requirements

    _seed(session)

    before = compute_case_requirements(CASE)
    assert before.nationalityClass is None, "gate should be blind before any nationality is written"
    titles_before = {r.title for r in before.requirements}
    assert "Long-stay work visa (VLS-TS)" in titles_before, (
        "unknown nationality fail-safes to THIRD_COUNTRY, so the visa item applies"
    )
    assert "EU/EEA worker right of residence" not in titles_before

    assert sync_nationality_to_case(session, CASE, "FR") is True
    assert _nationality_in_draft(session) == "FR"

    after = compute_case_requirements(CASE)
    assert after.nationalityClass == "OWN_NATIONAL", "FR national moving to FR is returning home"
    titles_after = {r.title for r in after.requirements}
    assert "EU/EEA worker right of residence" in titles_after
    assert "Long-stay work visa (VLS-TS)" not in titles_after
    assert "Long-stay work visa (VLS-TS)" in after.nationalityWaived, (
        "a suppressed requirement must be STATED, not silently dropped"
    )
    assert "Signed employment contract" in titles_after, "unscoped items apply to every class"


def test_third_country_nationality_is_recorded_not_merely_defaulted(session):
    """Andrea's case: VE is THIRD_COUNTRY, which is what she already got by accident.
    The point of writing it is that the engine now SAYS so instead of guessing."""
    from backend.app.services.nationality_sync import sync_nationality_to_case
    from backend.app.services.requirements_builder import compute_case_requirements

    _seed(session)
    sync_nationality_to_case(session, CASE, "VE")

    result = compute_case_requirements(CASE)
    assert result.nationalityClass == "THIRD_COUNTRY"
    assert "Long-stay work visa (VLS-TS)" in {r.title for r in result.requirements}


# ---------------------------------------------------------------------------
# Precedence and safety.
# ---------------------------------------------------------------------------


def test_an_existing_nationality_is_never_overwritten(session):
    """An HR correction outranks a later OCR read. Silently clobbering a human's
    correction with a machine's guess is the failure this guards."""
    from backend.app.services.nationality_sync import sync_nationality_to_case

    _seed(session, draft=json.dumps({"relocationBasics": {}, "employeeProfile": {"nationality": "FR"}}))

    assert sync_nationality_to_case(session, CASE, "VE") is False
    assert _nationality_in_draft(session) == "FR"


def test_blank_nationality_is_a_noop(session):
    from backend.app.services.nationality_sync import sync_nationality_to_case

    _seed(session)
    for blank in (None, "", "   "):
        assert sync_nationality_to_case(session, CASE, blank) is False
    assert _nationality_in_draft(session) is None


def test_missing_wizard_row_is_created(session):
    """809 relocation_cases have no wizard row at all. Those cases must still be able
    to record a nationality, or the capture path helps only the cases already fine."""
    from backend.app.services.nationality_sync import sync_nationality_to_case

    # No models.Case row seeded — only the relocation_cases side exists.
    session.execute(
        text(
            "INSERT INTO relocation_cases (id, origin_country_code, dest_country_code)"
            " VALUES (:id, 'ES', 'IE')"
        ),
        {"id": CASE},
    )
    session.commit()

    assert sync_nationality_to_case(session, CASE, "VE") is True
    assert _nationality_in_draft(session) == "VE"


def test_unknown_case_id_does_not_raise(session):
    from backend.app.services.nationality_sync import sync_nationality_to_case

    assert sync_nationality_to_case(session, "no-such-case", "VE") is True


# ---------------------------------------------------------------------------
# Wiring: the confirm path must actually call it.
# ---------------------------------------------------------------------------


def _handler_source(name: str) -> str:
    src = ROUTER.read_text()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(src, node) or ""
    raise AssertionError(f"{name} not found — did it get renamed?")


def _calls_in(src: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                names.add(fn.id)
            elif isinstance(fn, ast.Attribute):
                names.add(fn.attr)
    return names


def test_confirm_path_back_propagates_nationality():
    """`PUT /employee/cases/{id}/profile` is the confirm step — the one place a
    nationality becomes real. Extraction deliberately writes nothing (AIQ-1859), so
    hooking OCR instead would both break that contract and capture unconfirmed data."""
    assert "sync_nationality_to_case" in _calls_in(_handler_source("upsert_profile_employee"))


def test_ocr_extract_still_writes_nothing():
    """Guards the AIQ-1859 contract against this change: the sync must NOT be called
    from the read-only extraction endpoint."""
    assert "sync_nationality_to_case" not in _calls_in(_handler_source("ocr_passport"))
