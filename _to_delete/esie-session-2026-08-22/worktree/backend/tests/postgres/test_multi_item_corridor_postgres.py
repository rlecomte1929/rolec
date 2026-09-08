"""[AIQ-1852] A corridor with more than one requirement_item must not 500 on Postgres.

THE INCIDENT THIS PINS
----------------------
PR #1864 shipped with 37 green tests and 500'd on the first real call. `POST
/api/admin/attestations` inserts one `corridor_attestation_items` row per approved
requirement_item (`attestation.py:300`), so a corridor with ONE item is a single-row INSERT
and a corridor with TWO is a multi-row INSERT. Only the second shape reaches SQLAlchemy's
`insertmanyvalues` path, which matches result rows back to parameter sets by a sentinel — and
that match fails when a Python `str` is sent to a real `uuid` column and comes back a `UUID`:

    sqlalchemy.exc.InvalidRequestError: Can't match sentinel values in result set to
    parameter sets; key '…' was not found. There may be a mismatch between the datatype
    passed to the DBAPI driver vs. that which it returns in a result row.

Fixed in #1865 (`Uuid(as_uuid=False)` + `implicit_returning=False`).

**The item count is the whole point of this test.** One item passes on the broken code. Do not
"simplify" the fixture down to a single requirement — that silently removes the only thing
being tested.

WHY IT LIVES IN THE POSTGRES LANE
---------------------------------
Two conditions are both required, and the sqlite suite can satisfy neither:
  1. a real `uuid` column type — sqlite has none, so the mismatch cannot exist;
  2. a schema built from the MIGRATION, not from the models — see this package's conftest.

PROVEN TO DISCRIMINATE (2026-08-16, postgres:16, schema from the migration):
    pre-#1865  c35f696b -> FAILS with the sentinel error above
    current    2443798e -> passes
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime

import pytest

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

pytestmark = pytest.mark.postgres

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import models  # noqa: E402
from backend.app.auth_deps import require_admin  # noqa: E402
from backend.app.db import SessionLocal  # noqa: E402
from backend.main import app  # noqa: E402

ADMIN = {"id": "admin-1", "email": "admin@relopass.com", "is_admin": True, "role": "ADMIN"}

client = TestClient(app)


@pytest.fixture(autouse=True)
def _admin_auth():
    app.dependency_overrides[require_admin] = lambda: ADMIN
    yield
    app.dependency_overrides.pop(require_admin, None)


def _seed_corridor(n_items: int) -> str:
    """Seed `n_items` approved, legal-pillar requirements under a unique country key."""
    country = f"IRELAND_AIQ1852_{uuid.uuid4().hex[:8]}"
    pillars = ["EMPLOYMENT", "IDENTITY", "RESIDENCE", "SOCIAL_SECURITY"]
    with SessionLocal() as db:
        for i in range(n_items):
            db.add(models.RequirementItem(
                id=str(uuid.uuid4()),
                country_code=country,
                purpose="employment",
                pillar=pillars[i % len(pillars)],
                title=f"AIQ-1852 requirement {i}",
                description=f"Synthetic requirement {i} for the multi-item insert path.",
                severity="WARN",
                owner="EMPLOYEE",
                required_fields_json="[]",
                citations_json='[{"url": "https://www.irishimmigration.ie/example"}]',
                verification_status="corpus_grounded",
                review_status="approved",
                last_verified_at=datetime.utcnow(),
            ))
        db.commit()
    return country


def _create(country: str):
    return client.post("/api/admin/attestations", json={
        "country_code": country,
        "purpose": "employment",
        "reviewer_org": "Example Solicitors LLP",
        "reviewer_name": "Aoife Ni Bhriain",
        "reviewer_email": "aoife@example.ie",
        "reviewer_credential": "IE-LS-4321",
    })


def test_the_columns_under_test_are_really_uuid():
    """Guard the guard.

    Every assertion below is meaningless if the table came out `varchar` — that is the exact
    state in which the broken code passed 22/22. Fail loudly here rather than reporting a
    green run that proved nothing.
    """
    from sqlalchemy import text

    from backend.app.db import engine

    with engine.connect() as conn:
        types = dict(conn.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'corridor_attestation_items' "
            "AND column_name IN ('id', 'request_id')"
        )).all())
    assert types == {"id": "uuid", "request_id": "uuid"}, (
        f"expected real uuid columns, got {types}. The schema was built from the models "
        "instead of the migration — see backend/tests/postgres/conftest.py."
    )


def test_a_multi_item_corridor_returns_201_not_500():
    """The regression. Four items => a multi-row INSERT => the #1864 failure shape."""
    country = _seed_corridor(4)

    resp = _create(country)

    assert resp.status_code == 201, (
        f"multi-item corridor returned {resp.status_code}, not 201. This is the #1864 "
        f"regression — a uuid/str mismatch on the multi-row insert. Body: {resp.text[:600]}"
    )
    items = resp.json()["request"]["items"]
    assert len(items) == 4, f"expected all 4 requirements snapshotted, got {len(items)}"


def test_the_rows_are_actually_persisted():
    """201 is not enough — the insert must have committed all four child rows.

    A future 'fix' that swallowed the error and returned 201 with a partial checklist would
    satisfy the status-code assertion and still lose an attestation item.
    """
    country = _seed_corridor(3)
    request_id = _create(country).json()["request"]["id"]

    with SessionLocal() as db:
        persisted = (
            db.query(models.CorridorAttestationItem)
            .filter(models.CorridorAttestationItem.request_id == request_id)
            .count()
        )
    assert persisted == 3, f"expected 3 committed attestation items, found {persisted}"


def test_a_single_item_corridor_also_passes_which_is_why_it_proves_nothing():
    """The control, kept deliberately.

    A one-item corridor is a single-row INSERT: it never reaches insertmanyvalues and passes
    even on the broken commit. Its presence documents why the fixture above uses four.
    """
    country = _seed_corridor(1)
    assert _create(country).status_code == 201
