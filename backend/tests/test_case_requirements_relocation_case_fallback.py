"""[AIQ-1902] A case whose route lives only in `relocation_cases` still gets its dossier.

`compute_case_requirements` loads the case through `crud.get_case`, which reads
`wizard_cases` and nothing else. A case can be fully populated in `relocation_cases` — the
canonical, HR-facing table — while its `wizard_cases` row is empty. The destination then
resolved to "UNKNOWN", the fail-closed branch returned `_not_covered`, and the HR cockpit
rendered "No permit mapping for this destination yet." on a case whose destination is
plainly known.

Measured in production 2026-08-17, case 6ecadafe-0fdb-43c5-b8dc-0284e323cf51 (Andrea,
ES→IE):

    wizard_cases      dest_country = ''   purpose = ''
                      draft_json   = {"relocationBasics": {}, "employeeProfile": {}, …}
    relocation_cases  dest_country_code = 'IE'   origin_country_code = 'ES'
    requirement_items IRELAND, review_status='approved', purpose='employment' → 14 rows

The fixtures below reproduce exactly that split. The sibling case (Denis, NO→FR) already
worked because its `wizard_cases` row carries `FR` — which is why a frontend-only change
would have fixed one of the two reported cases and left the other broken.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app import models

ANDREA = "6ecadafe-0fdb-43c5-b8dc-0284e323cf51"
EMPTY_DRAFT = '{"relocationBasics": {}, "employeeProfile": {}, "familyMembers": {}, "assignmentContext": {}}'


def _requirement(i: int) -> models.RequirementItem:
    return models.RequirementItem(
        id=f"ie-req-{i}",
        country_code="IRELAND",
        purpose="employment",
        pillar="RESIDENCE",
        title=f"IE requirement {i}",
        description="…",
        severity="WARN",
        owner="EMPLOYEE",
        required_fields_json="[]",
        citations_json="[]",
        # Every real IE row is gated to third-country nationals; no nationality is on
        # file for this case, so the gate fail-safes to THIRD_COUNTRY and they all apply.
        applies_to_nationality_classes_json='["THIRD_COUNTRY"]',
        verification_status="corpus_grounded",
        review_status="approved",
        last_verified_at=datetime.utcnow(),
    )


@pytest.fixture()
def session(monkeypatch):
    engine = create_engine("sqlite://", future=True)
    # Whole metadata, not a hand-picked table list: the builder also reads
    # `source_records` when it assembles citations, and a partial schema turns that
    # into an OperationalError rather than a test result.
    models.Base.metadata.create_all(engine)
    # No ORM model exists for relocation_cases — raw DDL, mirroring the columns the
    # fallback reads.
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


def _seed(session, *, wizard_dest=None, wizard_purpose=None, reloc_dest="IE", reloc_origin="ES",
          requirements=14):
    session.add(
        models.Case(
            id=ANDREA,
            draft_json=EMPTY_DRAFT,
            dest_country=wizard_dest,
            purpose=wizard_purpose,
        )
    )
    for i in range(requirements):
        session.add(_requirement(i))
    if reloc_dest is not None or reloc_origin is not None:
        session.execute(
            text(
                "INSERT INTO relocation_cases (id, origin_country_code, dest_country_code)"
                " VALUES (:id, :o, :d)"
            ),
            {"id": ANDREA, "o": reloc_origin, "d": reloc_dest},
        )
    session.commit()


def test_case_6ecadafe_returns_its_14_ireland_requirements(session):
    """THE test the ticket asks for."""
    from backend.app.services.requirements_builder import compute_case_requirements

    _seed(session)  # the production shape: wizard row empty, relocation_cases says IE
    dto = compute_case_requirements(ANDREA)

    assert dto.covered is True, (
        "the destination is recorded in relocation_cases; returning not-covered is what "
        "produced 'No permit mapping for this destination yet.' in the HR cockpit"
    )
    assert dto.destCountry == "IRELAND"
    assert len(dto.requirements) == 14, (
        f"expected the 14 approved IE requirement_items, got {len(dto.requirements)}"
    )


def test_the_wizard_row_still_wins_when_it_has_a_destination(session):
    """The fallback only ADDS a source — it must not override a populated wizard row."""
    from backend.app.services.requirements_builder import compute_case_requirements

    # wizard says NORWAY, relocation_cases says IE. wizard wins, so the IE catalog
    # must NOT be returned.
    _seed(session, wizard_dest="NO", wizard_purpose="employment", reloc_dest="IE")
    dto = compute_case_requirements(ANDREA)
    assert dto.destCountry == "NORWAY"
    assert len(dto.requirements) == 0  # no NORWAY rows seeded here


def test_still_fails_closed_when_neither_table_knows_the_destination(session):
    """Guard the guard: the fallback must not weaken the fail-closed contract.

    An empty requirements list must never read as "nothing is required of you" — that is
    the whole point of `_not_covered`, and adding a data source must not erode it.
    """
    from backend.app.services.requirements_builder import compute_case_requirements

    _seed(session, reloc_dest=None, reloc_origin=None)
    dto = compute_case_requirements(ANDREA)
    assert dto.covered is False
    assert dto.requirements == [] or all(r.outcomeType != "action" for r in dto.requirements)


def test_an_in_country_move_is_still_detected_through_the_fallback(session):
    """A same-country move recorded only in relocation_cases must short-circuit.

    FR→FR rather than the ES→ES you might expect: `to_iso` resolves only the eight
    catalog countries, and Spain is not one of them — `to_iso("ES")` is None, so an
    ES→ES pair could never satisfy the origin == dest test and would prove nothing.
    """
    from backend.app.services.requirements_builder import compute_case_requirements

    _seed(session, reloc_dest="FR", reloc_origin="FR")
    dto = compute_case_requirements(ANDREA)
    # The in-country answer is STATED, never an empty list.
    assert dto.requirements, "an in-country move must say so explicitly"
    assert all(r.outcomeType == "nothing_to_do" for r in dto.requirements)
