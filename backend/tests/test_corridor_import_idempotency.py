"""Corridor-import idempotency: a duplicate import inserts ZERO new rows.

On 2026-08-15 the Norway (FR→NO) corridor import was accidentally run twice and
created duplicate requirement rows. The upsert funnel
(``crud.create_requirement_item``) matches the natural key
``(country_code, purpose, title)`` — but until this guard it did so only in
application code, as a SELECT-then-INSERT with no database constraint behind it.
Two racing imports both pre-select nothing and both insert; a writer that
bypasses the funnel duplicates freely; and once duplicates exist, ``.first()``
serves an arbitrary one of them. The knowledge graph's whole value is being the
source that stays accurate, so silent duplication is not a cosmetic bug.

Three layers are pinned here, all against the REAL Norway corridor seed
(``backend/seeds/requirements/norway.yaml`` — the exact import that ran twice):

  (a) the row-count invariant: importing the corridor twice (or N times) leaves
      the table byte-for-byte at the run-once row set — zero new rows;
  (b) the guard lives in the DATABASE: a writer that bypasses
      ``crud.create_requirement_item`` entirely cannot insert a duplicate either
      (``uq_requirement_items_country_purpose_title``, sqlite here, Postgres via
      migration 20261118000000);
  (c) the lost-pre-select race: the insert path runs
      ``ON CONFLICT (country_code, purpose, title) DO NOTHING``, so an import
      that raced past the pre-select inserts zero rows and converges on the row
      that won instead of duplicating it.
"""
from __future__ import annotations

import os
from datetime import datetime

import pytest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app import crud, models
from backend.scripts.seed_requirements import build_payloads

NORWAY_SEED = os.path.join(
    os.path.dirname(__file__), "..", "seeds", "requirements", "norway.yaml"
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", future=True)
    models.Base.metadata.create_all(engine, tables=[models.RequirementItem.__table__])
    with sessionmaker(bind=engine)() as session:
        yield session


def _norway_payloads():
    """The 2026-08-15 corridor import's own fixture: the committed FR→NO seed."""
    with open(NORWAY_SEED, "r", encoding="utf-8") as fh:
        seed = yaml.safe_load(fh)
    payloads = build_payloads(seed)
    assert len(payloads) >= 5, "the fixture must be a real corridor, not a stub"
    return payloads


def _run_import(db, payloads):
    """One full corridor import, exactly as seed_requirements.main() drives it."""
    now = datetime.utcnow()
    for p in payloads:
        crud.create_requirement_item(db, dict(p, last_verified_at=now))


def _row_count(db) -> int:
    return db.query(models.RequirementItem).count()


def _row_keys(db):
    return {
        (r.id, r.country_code, r.purpose, r.title)
        for r in db.query(models.RequirementItem).all()
    }


# ── (a) the double-import row-count invariant ───────────────────────────────────────


def test_double_import_of_the_norway_corridor_inserts_zero_new_rows(db):
    """The 2026-08-15 incident, replayed: the second import must be a no-op."""
    payloads = _norway_payloads()

    _run_import(db, payloads)
    after_first = _row_count(db)
    assert after_first == len(payloads), "first import loads every requirement once"

    _run_import(db, payloads)  # the accidental second run
    assert _row_count(db) == after_first, (
        "a duplicate corridor import inserted new rows — the idempotency guard is broken"
    )


def test_importing_n_times_produces_the_same_row_set_as_importing_once(db):
    """Not just the count: the surviving (id, natural key) set is identical, so N runs
    end in the same DB state as one run."""
    payloads = _norway_payloads()
    _run_import(db, payloads)
    baseline = _row_keys(db)

    for _ in range(3):
        _run_import(db, payloads)

    assert _row_keys(db) == baseline


def test_a_reimport_updates_content_in_place_rather_than_inserting(db):
    """Idempotent does not mean frozen: a re-import with revised content converges on
    the SAME row (updated in place), never on a second one."""
    payloads = _norway_payloads()
    first = dict(payloads[0], last_verified_at=datetime(2026, 8, 15))
    crud.create_requirement_item(db, first)

    revised = dict(first, description="Revised wording from the re-import.")
    crud.create_requirement_item(db, revised)

    row = db.query(models.RequirementItem).one()
    assert row.description == "Revised wording from the re-import."


def test_reimport_does_not_clobber_review_status(db):
    """A human publish must survive a seed/Otto re-run that still says pending."""
    payloads = _norway_payloads()
    first = dict(payloads[0], last_verified_at=datetime(2026, 8, 15), review_status="pending")
    crud.create_requirement_item(db, first)
    row = db.query(models.RequirementItem).one()
    row.review_status = "approved"
    db.commit()

    again = dict(first, review_status="pending", description="Agent rewrite")
    crud.create_requirement_item(db, again)
    row = db.query(models.RequirementItem).one()
    assert row.review_status == "approved"
    assert row.description == "Agent rewrite"


def test_insert_without_review_status_lands_pending_not_approved(db):
    payloads = _norway_payloads()
    first = dict(payloads[0], last_verified_at=datetime(2026, 8, 15))
    first.pop("review_status", None)
    crud.create_requirement_item(db, first)
    row = db.query(models.RequirementItem).one()
    assert row.review_status == "pending"


# ── (b) the guard is a database constraint, not an application convention ───────────


def test_the_natural_key_is_enforced_by_the_database_not_just_the_funnel(db):
    """A writer that bypasses crud.create_requirement_item (a hand-rolled SQL load, an
    ORM add) cannot duplicate a requirement either: the unique constraint refuses it."""
    payloads = _norway_payloads()
    first = dict(payloads[0], last_verified_at=datetime(2026, 8, 15))
    crud.create_requirement_item(db, first)

    clone = dict(first, id="a-different-id-from-a-second-import-run")
    db.add(models.RequirementItem(**clone))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert _row_count(db) == 1


# ── (c) the lost-pre-select race converges instead of duplicating ───────────────────


def test_a_lost_pre_select_race_inserts_zero_rows_and_converges(db):
    """Simulate how 2026-08-15 actually duplicated: an import reaches its INSERT even
    though the row already exists (two runs both pre-selected nothing). The insert is
    ON CONFLICT (country_code, purpose, title) DO NOTHING, so it inserts ZERO rows,
    and the funnel converges on the row that won the race."""
    payloads = _norway_payloads()
    first = dict(payloads[0], last_verified_at=datetime(2026, 8, 15))
    winner = crud.create_requirement_item(db, first)

    racing = dict(first, id="id-from-the-racing-import")
    inserted = crud._insert_requirement_item_ignore_conflict(db, racing)
    db.commit()

    assert inserted == 0, "the conflicting insert must report zero rows inserted"
    assert _row_count(db) == 1
    survivor = db.query(models.RequirementItem).one()
    assert survivor.id == winner.id
