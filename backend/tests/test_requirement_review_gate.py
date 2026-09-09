"""The publication gate on `requirement_items`, and the two ways it could be defeated.

Before `review_status` existed there was no gate at all. A row was readable the instant
`COMMIT` returned — by authenticated employees via `requirements_builder`, and by anonymous
callers via `GET /api/public/corridor-requirements`, which takes no credentials. That is how
the first Otto-promoted France requirements and the whole Norway wedge reached the public
internet without a human seeing them.

`verification_status` looked like a gate and never was: no read path has ever filtered on it,
and the public endpoint strips it from the response. These tests pin the difference — one
column describes *how well sourced* content is, the other decides *whether it is served*.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import crud, models
from backend.app.services import verification_guard


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", future=True)
    models.Base.metadata.create_all(engine, tables=[models.RequirementItem.__table__])
    with sessionmaker(bind=engine)() as session:
        yield session


def _payload(title: str, **over):
    base = dict(
        id=f"id-{title}",
        country_code="NORWAY",
        purpose="employment",
        pillar="RESIDENCE",
        title=title,
        description="…",
        severity="WARN",
        owner="EMPLOYEE",
        required_fields_json="[]",
        citations_json="[]",
        verification_status="corpus_grounded",
        last_verified_at=datetime(2026, 8, 12),
    )
    base.update(over)
    return base


def test_an_unapproved_row_is_not_served(db):
    crud.create_requirement_item(db, _payload("Pending item", review_status="pending"))
    assert crud.list_requirements(db, "NORWAY") == []


def test_an_approved_row_is_served(db):
    crud.create_requirement_item(db, _payload("Approved item", review_status="approved"))
    assert [r.title for r in crud.list_requirements(db, "NORWAY")] == ["Approved item"]


def test_a_rejected_row_is_not_served(db):
    crud.create_requirement_item(db, _payload("Rejected item", review_status="rejected"))
    assert crud.list_requirements(db, "NORWAY") == []


def test_the_admin_surface_sees_what_it_must_approve(db):
    crud.create_requirement_item(db, _payload("Pending item", review_status="pending"))
    got = crud.list_requirements(db, "NORWAY", include_unapproved=True)
    assert [r.title for r in got] == ["Pending item"]


def test_provenance_is_not_a_gate(db):
    """`representative` content is served exactly like `expert_verified` content. The badge
    describes sourcing; it has never decided visibility, and conflating the two is what made
    the missing gate hard to see.

    The expert_verified row is created through the human sign-off path — since the
    verified-write guardrail (services/verification_guard), a generator insert can no
    longer claim that status directly (see test_verified_write_guardrail.py)."""
    for status in ("representative", "corpus_grounded"):
        crud.create_requirement_item(
            db, _payload(f"{status} item", verification_status=status, review_status="approved")
        )
    signed = crud.create_requirement_item(
        db,
        _payload("expert_verified item", verification_status="corpus_grounded", review_status="approved"),
    )
    verification_guard.mark_expert_verified(signed, verified_by="jane@relopass.com")
    db.commit()
    assert len(crud.list_requirements(db, "NORWAY")) == 3


def test_reseeding_cannot_un_approve_live_content(db):
    """The regression that would quietly break production.

    `create_requirement_item` upserts on (country_code, purpose, title), and every YAML seed
    now writes `review_status='pending'`. If the update branch synced that column, re-running
    `seed_requirements.py --file germany.yaml` would pull 16 approved rows back out of the
    product. It must be set on INSERT and carried on UPDATE.
    """
    crud.create_requirement_item(db, _payload("Employment letter", review_status="approved"))
    crud.create_requirement_item(
        db, _payload("Employment letter", review_status="pending", description="reworded")
    )
    rows = crud.list_requirements(db, "NORWAY")
    assert [r.title for r in rows] == ["Employment letter"]
    assert rows[0].review_status == "approved"
    assert rows[0].description == "reworded", "the seed's content still lands"




def test_a_new_row_defaults_to_pending_through_the_automated_funnel(db):
    """AIQ-1473 / 82c02e0f: every caller of crud.create_requirement_item is an automated
    producer (Otto promote, YAML seed, research stub). The funnel now defaults an omitted
    review_status to 'pending' so machine-written content waits for a human — it must not be
    served until reviewed, but is retrievable with include_unapproved for the review queue."""
    payload = _payload("Machine item")
    payload.pop("review_status", None)
    crud.create_requirement_item(db, payload)
    assert crud.list_requirements(db, "NORWAY") == []  # not served
    got = crud.list_requirements(db, "NORWAY", include_unapproved=True)
    assert [r.title for r in got] == ["Machine item"]  # awaiting a human


def test_a_legacy_orm_row_without_review_status_is_served(db):
    """The DB-level 'silence means approved' guarantee still holds for rows that predate the
    column or are written directly via the ORM (bypassing the automated funnel): the column
    server_default is 'approved', so such a row is served and does not go dark."""
    row = _payload("Legacy ORM row")
    row.pop("review_status", None)
    db.add(models.RequirementItem(**row))
    db.commit()
    assert [r.title for r in crud.list_requirements(db, "NORWAY")] == ["Legacy ORM row"]
