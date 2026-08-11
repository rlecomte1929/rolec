"""[AIQ-1819] `_vendor_names_for_rfq` ordered by a column that did not exist.

WHY THIS EXISTS
---------------
`backend/db/vendors.py:533` has always run:

    SELECT s.name FROM rfq_recipients rr
    LEFT JOIN suppliers s ON s.id = rr.vendor_id
    WHERE rr.rfq_id = :r ORDER BY rr.created_at

`rfq_recipients` had no `created_at`. Reproduced against production 2026-08-11:

    ERROR: 42703: column rr.created_at does not exist

It is reachable — `vendors.py:608`, inside `list_quote_conversations_for_employee`, a live
employee path. It has therefore raised on every single call since it was written.

WHY NOBODY NOTICED, WHICH IS THE REAL LESSON
--------------------------------------------
The function ends `except Exception: return None`, and the call site reads
`or "Service provider"`. So the failure rendered as a plausible generic label. Every employee
quote thread has shown "Service provider" instead of the vendor's name for the life of the
feature, and no error ever surfaced. A bare `except` around a query turns "this has never
worked" into "this looks fine".

WHY THIS TEST IS NOT WRITTEN AGAINST SQLite
-------------------------------------------
`backend/tests/test_rfq_recipient_identity.py` and `test_employee_quote_vendors.py` both build
`rfq_recipients` with hand-written DDL inside the test file ("Mirrors the production DDL, with
jsonb -> TEXT for SQLite"). A column present in the fixture and absent in production passes
green forever — that is exactly the blindness that hid this bug, and it is the same mechanism
that let `rfqs.created_by_user_id` reach prod with the wrong type twice. So: real Postgres, and
the schema below deliberately OMITS `created_at` so the migration is what adds it.

WHAT IS PINNED
--------------
- The pre-migration schema really does reject the query (42703). If that ever stops being true
  the migration is solving a problem that no longer exists — fail loudly, not silently.
- After the migration the query runs and orders by insertion time.
- The backfill preserves real chronology: `invited_at` when present, else the parent RFQ's
  `created_at`. All 135 production rows had one of those, so none needed `now()`.
- `_vendor_names_for_rfq` returns the vendor's NAME, not `None` — i.e. the caller stops
  falling back to "Service provider".

RUNNING — a throwaway local Postgres, never production
------------------------------------------------------
`integration`-marked, so CI's `-m "not integration"` run skips it.

    docker run -d --name rfqpg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=rfqtest \
      -p 55437:5432 postgres:15-alpine

    DATABASE_URL=postgresql://postgres:test@127.0.0.1:55437/rfqtest \
      pytest backend/tests/integration/test_rfq_recipient_ordering.py -v
"""
from __future__ import annotations

import os
import pathlib
import uuid

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import DatabaseError  # noqa: E402

from backend.db.misc import MiscMixin  # noqa: E402
from backend.db.vendors import VendorsMixin  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "")
_IS_PG = DATABASE_URL.startswith("postgres")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _IS_PG, reason="needs a real Postgres; see the module docstring"),
]

MIGRATION = (
    pathlib.Path(__file__).resolve().parents[3]
    / "supabase"
    / "migrations"
    / "20261028000000_rfq_recipients_created_at.sql"
)

# Mirrors production's rfq_recipients as measured 2026-08-11 (information_schema), MINUS
# created_at — which is the whole point. Adding it here would reproduce the fixture blindness
# this test exists to avoid.
SCHEMA = """
DROP TABLE IF EXISTS public.rfq_recipients CASCADE;
DROP TABLE IF EXISTS public.rfqs CASCADE;
DROP TABLE IF EXISTS public.suppliers CASCADE;

CREATE TABLE public.suppliers (
    id   text PRIMARY KEY,
    name text
);

CREATE TABLE public.rfqs (
    id         uuid PRIMARY KEY,
    created_at timestamptz
);

CREATE TABLE public.rfq_recipients (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id             uuid NOT NULL,
    vendor_id          text NOT NULL,
    status             text NOT NULL DEFAULT 'sent',
    last_activity_at   timestamptz,
    token_hash         text,
    invited_email      text,
    invited_at         timestamptz,
    expires_at         timestamptz,
    first_viewed_at    timestamptz,
    quote_submitted_at timestamptz,
    revoked_at         timestamptz
);
"""

THE_QUERY = (
    "SELECT s.name AS name FROM rfq_recipients rr "
    "LEFT JOIN suppliers s ON s.id = rr.vendor_id "
    "WHERE rr.rfq_id = :r ORDER BY rr.created_at"
)


class _Host(MiscMixin, VendorsMixin):
    """Minimal carrier so the real method under test runs, not a copy of it."""

    def __init__(self, engine) -> None:
        self.engine = engine
        self._initialized = True


@pytest.fixture()
def engine():
    eng = create_engine(DATABASE_URL, future=True)
    with eng.begin() as c:
        for stmt in filter(None, (s.strip() for s in SCHEMA.split(";"))):
            c.execute(text(stmt))
    yield eng
    eng.dispose()


@pytest.fixture()
def seeded(engine):
    """One RFQ, three recipients, deliberately inserted out of chronological order.

    Two carry `invited_at`; the third carries none, so the backfill has to fall back to the
    parent RFQ's created_at. That is the exact 68/67 split measured on production.
    """
    rfq_id = uuid.uuid4()
    with engine.begin() as c:
        c.execute(
            text("INSERT INTO rfqs (id, created_at) VALUES (:i, '2026-01-01T00:00:00Z')"),
            {"i": rfq_id},
        )
        for sid, nm in (("s-b", "Bravo Movers"), ("s-a", "Alpha Relocation"), ("s-c", "Charlie GmbH")):
            c.execute(text("INSERT INTO suppliers (id, name) VALUES (:i, :n)"), {"i": sid, "n": nm})
        # inserted C, A, B — invited A, B; C has no invited_at
        c.execute(
            text(
                "INSERT INTO rfq_recipients (rfq_id, vendor_id, invited_at) VALUES "
                "(:r,'s-c', NULL),"
                "(:r,'s-a','2026-03-01T10:00:00Z'),"
                "(:r,'s-b','2026-03-01T11:00:00Z')"
            ),
            {"r": rfq_id},
        )
    return rfq_id


def _apply_migration(engine) -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    with engine.begin() as c:
        c.exec_driver_sql(sql)


def test_the_migration_file_exists():
    """A missing file would make every test below skip-shaped rather than fail-shaped."""
    assert MIGRATION.is_file(), f"migration not found at {MIGRATION}"


def test_the_query_fails_before_the_migration(engine, seeded):
    """Characterisation: this is the production bug, executable.

    Kept permanently. If it ever stops raising, the schema gained created_at by some other
    route and the migration below is redundant — which is worth knowing loudly.
    """
    with pytest.raises(DatabaseError) as exc:
        with engine.connect() as c:
            c.execute(text(THE_QUERY), {"r": str(seeded)}).fetchall()
    assert "created_at" in str(exc.value), str(exc.value)


def test_the_real_function_returns_none_before_the_migration(engine, seeded):
    """The bare `except` is why this shipped: a hard SQL error reads as 'no vendors'."""
    assert _Host(engine)._vendor_names_for_rfq(str(seeded)) is None


def test_the_query_works_after_the_migration(engine, seeded):
    _apply_migration(engine)
    with engine.connect() as c:
        names = [r[0] for r in c.execute(text(THE_QUERY), {"r": str(seeded)}).fetchall()]
    assert names == ["Charlie GmbH", "Alpha Relocation", "Bravo Movers"], names


def test_the_backfill_uses_real_chronology_not_the_migration_time(engine, seeded):
    """Existing rows must not all collapse onto now().

    Charlie has no invited_at, so it inherits the RFQ's 2026-01-01. Alpha and Bravo keep their
    own invited_at. A flat now() stamp would make all three equal and destroy the ordering the
    column exists to provide.
    """
    _apply_migration(engine)
    with engine.connect() as c:
        rows = dict(
            c.execute(
                text(
                    "SELECT s.name, rr.created_at FROM rfq_recipients rr "
                    "JOIN suppliers s ON s.id = rr.vendor_id WHERE rr.rfq_id = :r"
                ),
                {"r": str(seeded)},
            ).fetchall()
        )
    assert rows["Charlie GmbH"].year == 2026 and rows["Charlie GmbH"].month == 1
    assert rows["Alpha Relocation"].month == 3 and rows["Alpha Relocation"].hour == 10
    assert rows["Bravo Movers"].month == 3 and rows["Bravo Movers"].hour == 11
    assert len({v for v in rows.values()}) == 3, "backfill collapsed distinct rows onto one time"


def test_new_rows_get_a_default(engine, seeded):
    _apply_migration(engine)
    with engine.begin() as c:
        c.execute(
            text("INSERT INTO rfq_recipients (rfq_id, vendor_id) VALUES (:r, 's-a')"),
            {"r": seeded},
        )
        n = c.execute(text("SELECT count(*) FROM rfq_recipients WHERE created_at IS NULL")).scalar()
    assert n == 0


def test_the_migration_is_idempotent(engine, seeded):
    _apply_migration(engine)
    _apply_migration(engine)  # must not raise
    with engine.connect() as c:
        n = c.execute(text("SELECT count(*) FROM rfq_recipients")).scalar()
    assert n == 3, "re-running the migration changed the data"


def test_the_employee_sees_a_vendor_name_not_service_provider(engine, seeded):
    """The user-visible point of the whole ticket.

    `list_quote_conversations_for_employee` reads
    `self._vendor_names_for_rfq(...) or "Service provider"`. While the query raised, the
    fallback was unconditional.
    """
    host = _Host(engine)
    _apply_migration(engine)
    label = host._vendor_names_for_rfq(str(seeded)) or "Service provider"
    assert label != "Service provider"
    # three recipients -> "<first> (+2)", first by insertion time
    assert label == "Charlie GmbH (+2)", label
