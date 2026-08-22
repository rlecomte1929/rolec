"""Regression: GET /api/public/corridor-requirements must serve, for every corridor.

THE INCIDENT (2026-08-22, deploy 65659473, request_id 462dd172-ea94-495f-9680-bcba05129470).
The endpoint returned 500 for FR→NO, IN→DE and ES→IE simultaneously, and
`GET /api/cases/{id}/requirements` with it:

    ProgrammingError: column requirement_items.verified_by does not exist

Not a bad row and not the projection. PR #1963 declared `verified_by`/`verified_at` on the
`RequirementItem` ORM model in the same merge as the migration that adds them, and migrations
here apply OUT OF BAND (CLAUDE.md, "Migration discipline"). A *mapped* column goes into the
SELECT list of every query against the table, so the whole table's traffic failed at once —
which is why it looked like a serving-layer fault rather than schema drift.

WHY THE EXISTING SUITE WAS GREEN THROUGHOUT. `test_public_corridor.py` monkeypatches
`crud.list_requirements` to canned `SimpleNamespace` rows, so no SELECT is ever emitted and
no mapped column is ever read. It asserts the projection, which was never broken.

So this file deliberately does NOT patch the query out. It seeds real `RequirementItem` rows
and lets the real `crud.list_requirements` → `_base_items` → `apply_rules` chain run, for two
corridors. Any future mapped column the database does not have fails here the way it fails in
production, instead of after the deploy.

The PR-time guard for the same class is `scripts/check_column_read_before_apply.py`, taught
the ORM-declaration form in this change; see backend/tests/test_column_read_before_apply_guard.py.
"""
from __future__ import annotations

import os
from datetime import datetime

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.app import models  # noqa: E402
from backend.app.routers import public_corridor  # noqa: E402
from backend.main import app  # noqa: E402

client = TestClient(app)

# (country_code, pillar, title) per destination. Two corridors, as the acceptance asks.
_SEED = {
    "IRELAND": [
        ("IMMIGRATION", "Critical Skills Employment Permit"),
        ("RESIDENCE", "Register with immigration (IRP)"),
    ],
    "NORWAY": [
        ("RESIDENCE", "Residence registration (folkeregister)"),
        ("SOCIAL_SECURITY", "National Insurance registration (folketrygden)"),
    ],
}


def _row(country: str, pillar: str, title: str) -> models.RequirementItem:
    return models.RequirementItem(
        id=f"{country.lower()}-{pillar.lower()}",
        country_code=country,
        purpose="employment",
        pillar=pillar,
        title=title,
        description="Seeded for the serving regression. Indicative.",
        severity="WARN",
        owner="EMPLOYEE",
        required_fields_json="[]",
        citations_json="[]",
        review_status="approved",
        verification_status="representative",
        last_verified_at=datetime(2026, 8, 22),
    )


@pytest.fixture()
def seeded_db(monkeypatch):
    """A real engine with the real RequirementItem table, wired into the router.

    StaticPool + a shared in-memory database: the router opens its own session, and a
    default in-memory SQLite engine would hand it a different, empty database.
    """
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine, tables=[models.RequirementItem.__table__])
    Session = sessionmaker(bind=engine, future=True)
    with Session() as session:
        for country, items in _SEED.items():
            for pillar, title in items:
                session.add(_row(country, pillar, title))
        session.commit()
    # The router does `with SessionLocal() as db:` — swap that symbol, keep the real query.
    monkeypatch.setattr(public_corridor, "SessionLocal", Session)
    return Session


@pytest.mark.parametrize(
    ("origin", "dest", "expect_catalog"),
    [("ES", "IE", "IRELAND"), ("FR", "NO", "NORWAY")],
)
def test_corridor_requirements_serves_200_and_non_empty(seeded_db, origin, dest, expect_catalog):
    """The acceptance criterion: 200 + a non-empty list, per corridor, via the real SELECT."""
    resp = client.get(
        f"/api/public/corridor-requirements?from={origin}&to={dest}&employee_type=LTA"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["corridor"] == {"from": origin, "to": expect_catalog}
    assert body["requirements"], f"{origin}->{dest} served an empty list"
    assert body["coverage_note"] is None


def test_every_mapped_column_is_selectable(seeded_db):
    """Reads through `crud.list_requirements` — the single funnel BOTH readers use.

    `requirements_builder` (the case path, which 500'd alongside the public endpoint) and
    `public_corridor` share this one query, so covering it here covers both.
    """
    from backend.app import crud

    with seeded_db() as db:
        rows = crud.list_requirements(db, "IRELAND", "employment")
    assert rows, "seeded IRELAND rows did not come back"
    for column in models.RequirementItem.__table__.columns:
        # In the emitted SELECT list — a column the database lacks raises before this point.
        getattr(rows[0], column.key)


def test_a_missing_column_actually_fails_this_harness():
    """Proves the two tests above DISCRIMINATE, which is not self-evident.

    `Base.metadata.create_all()` builds the table from the model, so the model and the
    fixture can never disagree and no SQLite test can spontaneously reproduce the incident
    (this is the standing `create_all is blind to model/migration drift` trap). Without this
    test, the file above would pass equally well against a model mapping a column nothing has
    — i.e. it would look like protection while proving only that the projection works.

    So build the table WITHOUT `verified_by`, exactly as production stood at 18:42 UTC, and
    assert the same query raises. Note this is the harness's floor, not a CI gate against
    prod: CI has no production schema. The gate that would have BLOCKED the incident is
    scripts/check_column_read_before_apply.py, taught the ORM-declaration form in this change.
    """
    from sqlalchemy import Table
    from sqlalchemy.exc import OperationalError

    from backend.app import crud

    engine = create_engine(
        "sqlite://", future=True,
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    full = models.RequirementItem.__table__
    assert "verified_by" in full.columns, "model no longer maps verified_by — update this test"

    # Same table, minus the column production was missing.
    from sqlalchemy import MetaData
    md = MetaData()
    Table(
        full.name, md,
        *[c._copy() for c in full.columns if c.name != "verified_by"],
    ).create(engine)

    Session = sessionmaker(bind=engine, future=True)
    with Session() as db:
        with pytest.raises(OperationalError) as exc:
            crud.list_requirements(db, "IRELAND", "employment")
    assert "verified_by" in str(exc.value), str(exc.value)
