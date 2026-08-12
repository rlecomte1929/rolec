"""[O1] FR->NO evidence must actually reach the screen.

WHAT WENT WRONG, AND WHY NOTHING CAUGHT IT
------------------------------------------
`requirement_items.citations_json` is meant to hold `source_records.id` values. For the Norway
rows it held RAW URLs. `requirements_builder.py:263-266` resolves each citation against a
source-record map and silently drops anything unresolvable:

    citations = [_source_dto(source_map[cid])
                 for cid in item.get("citations", []) if cid in source_map]

So the correct official URL was in the database and the user saw nothing. There was no error, no
empty-state, no log line — the list was simply shorter. Measured in production 2026-08-12 before
the fix: 90 requirement items carried citations, **27 resolved**. 63 items rendered zero evidence
while holding the right link.

That is why the first test here asserts the DROP, and the rest assert the fix. A test that only
checked "citations_json is non-empty" would have passed throughout — which is precisely how this
survived.

WHY REAL POSTGRES
-----------------
The migration is the artifact under test: fixed UUIDs, `ON CONFLICT (content_hash) DO NOTHING`,
`sha256()`, and a `jsonb_array_elements_text ... WITH ORDINALITY` rewrite. None of that runs on
SQLite, and a hand-rolled fixture would let the migration and the test drift — the failure mode
that hid `rfq_recipients.created_at` for months.

RUNNING — a throwaway local Postgres, never production
------------------------------------------------------
`integration`-marked, so CI's `-m "not integration"` run skips it.

    docker run -d --name o1pg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=o1test \
      -p 55439:5432 postgres:15-alpine

    DATABASE_URL=postgresql://postgres:test@127.0.0.1:55439/o1test \
      pytest backend/tests/integration/test_frno_citations_resolve.py -v
"""
from __future__ import annotations

import os
import pathlib

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, text  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "")
_IS_PG = DATABASE_URL.startswith("postgres")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _IS_PG, reason="needs a real Postgres; see the module docstring"),
]

MIGRATION = (
    pathlib.Path(__file__).resolve().parents[3]
    / "supabase" / "migrations" / "20261031000000_frno_source_records.sql"
)

#: Mirrors the production columns of both tables as measured 2026-08-12.
SCHEMA = """
DROP TABLE IF EXISTS public.requirement_items CASCADE;
DROP TABLE IF EXISTS public.source_records CASCADE;

CREATE TABLE public.source_records (
    id varchar PRIMARY KEY, country_code varchar, url varchar NOT NULL, title varchar NOT NULL,
    publisher_domain varchar NOT NULL, retrieved_at timestamp NOT NULL, snippet text,
    content_hash varchar NOT NULL UNIQUE);

CREATE TABLE public.requirement_items (
    id varchar PRIMARY KEY, country_code varchar, purpose varchar NOT NULL,
    pillar varchar NOT NULL, title varchar NOT NULL, description text NOT NULL,
    severity varchar NOT NULL, owner varchar NOT NULL, required_fields_json text NOT NULL,
    citations_json text NOT NULL, last_verified_at timestamp NOT NULL,
    verification_status text);
"""

SKATT = "https://www.skatteetaten.no/en/business-and-organisation/foreign/employer/tax-deduction-cards/"
UDI_D = "https://www.udi.no/en/word-definitions/d-number/"
UDI_EMP = "https://www.udi.no/en/word-definitions/employers-employing-someone-who-is-an-eueea-national-/"
UDI_REG = "https://www.udi.no/en/want-to-apply/residence-under-the-eueeu-regulations/employee-who-is-an-eueea-national/"
NAV = "https://www.nav.no/en/home/rules-and-regulations/relatert-informasjon/coming-from-an-eu-eea-country-to-work-in-norway"
CLEISS = "https://www.cleiss.fr/particuliers/venir/travailler/detachement/ue883.html"

#: The four "non-obvious" FR->NO requirements, seeded exactly as production holds them —
#: citations_json containing RAW URLs. Every Norway requirement exists twice, once per `purpose`.
SEED = [
    ("r1", "employment", "EMPLOYMENT", "Tax deduction card (skattekort) before first salary", [SKATT]),
    ("r2", "other", "EMPLOYMENT", "Tax deduction card (skattekort) before first salary", [SKATT]),
    ("r3", "employment", "IDENTITY", "D-number (stays under 6 months)", [SKATT, UDI_D]),
    ("r4", "other", "IDENTITY", "D-number (stays under 6 months)", [SKATT, UDI_D]),
    ("r5", "employment", "RESIDENCE", "Police registration for EU/EEA nationals (stays over 3 months)", [UDI_REG, UDI_EMP]),
    ("r6", "other", "RESIDENCE", "Police registration for EU/EEA nationals (stays over 3 months)", [UDI_REG, UDI_EMP]),
    ("r7", "employment", "SOCIAL_SECURITY", "A1 certificate for genuinely posted workers", [CLEISS, NAV]),
    ("r8", "other", "SOCIAL_SECURITY", "A1 certificate for genuinely posted workers", [CLEISS, NAV]),
    # An untargeted row, to prove the migration is scoped and leaves the rest alone.
    ("rX", "other", "HOUSING", "Long-term housing contract", []),
]

_RESOLVING = """
SELECT count(DISTINCT ri.id) FROM public.requirement_items ri
 WHERE EXISTS (SELECT 1 FROM jsonb_array_elements_text(ri.citations_json::jsonb) c(cid)
               JOIN public.source_records s ON s.id = c.cid)
"""


@pytest.fixture()
def engine():
    import json
    eng = create_engine(DATABASE_URL, future=True)
    with eng.begin() as c:
        for stmt in filter(None, (s.strip() for s in SCHEMA.split(";"))):
            c.execute(text(stmt))
        for rid, purpose, pillar, title, cites in SEED:
            c.execute(
                text(
                    "INSERT INTO public.requirement_items (id, country_code, purpose, pillar, "
                    "title, description, severity, owner, required_fields_json, citations_json, "
                    "last_verified_at, verification_status) VALUES (:i,'NORWAY',:p,:pl,:t,'d',"
                    "'BLOCKER','o','[]',:c, now(), 'corpus_grounded')"
                ),
                {"i": rid, "p": purpose, "pl": pillar, "t": title, "c": json.dumps(cites)},
            )
    yield eng
    eng.dispose()


def _apply(engine) -> None:
    # Raw DBAPI cursor, not exec_driver_sql: SQLAlchemy passes an empty immutabledict as
    # parameters and psycopg2 rejects it with "immutabledict is not a sequence". The migration
    # is a multi-statement script with no bind params, so the driver runs it directly.
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute(MIGRATION.read_text(encoding="utf-8"))
        raw.commit()
    finally:
        raw.close()


def test_the_migration_file_exists():
    assert MIGRATION.is_file(), f"migration not found at {MIGRATION}"


def test_before_the_migration_no_citation_resolves(engine):
    """Characterisation of the production bug, kept executable.

    Every one of these rows has the correct official URL. None of it reaches the DTO, because
    the builder drops citations it cannot resolve. If this ever stops being zero, the data got
    fixed by some other route and this migration is redundant — worth knowing loudly.
    """
    with engine.connect() as c:
        assert c.execute(text(_RESOLVING)).scalar() == 0


def test_every_targeted_requirement_resolves_at_least_one_citation(engine):
    _apply(engine)
    with engine.connect() as c:
        rows = c.execute(text(
            "SELECT ri.id, count(s.id) FROM public.requirement_items ri "
            "CROSS JOIN LATERAL jsonb_array_elements_text(ri.citations_json::jsonb) cc(cid) "
            "LEFT JOIN public.source_records s ON s.id = cc.cid "
            "WHERE ri.title <> 'Long-term housing contract' GROUP BY ri.id ORDER BY ri.id"
        )).fetchall()
    assert len(rows) == 8, f"expected the 8 targeted rows, got {rows}"
    unresolved = [r[0] for r in rows if r[1] == 0]
    assert not unresolved, f"these still render no evidence: {unresolved}"


def test_the_demo_requirement_carries_the_official_quote(engine):
    """The North Star bar is a requirement an HR generalist would not know to look for, that is
    accurate. This is that requirement, and this is the sentence that makes it checkable."""
    _apply(engine)
    with engine.connect() as c:
        snippet, domain = c.execute(text(
            "SELECT s.snippet, s.publisher_domain FROM public.requirement_items ri "
            "CROSS JOIN LATERAL jsonb_array_elements_text(ri.citations_json::jsonb) cc(cid) "
            "JOIN public.source_records s ON s.id = cc.cid WHERE ri.id = 'r1'"
        )).one()
    assert "50 percent" in snippet, snippet
    assert domain == "www.skatteetaten.no"


def test_an_unresolvable_citation_is_kept_not_dropped(engine):
    """Dropping it would repeat this migration's own bug one layer down."""
    _apply(engine)
    with engine.begin() as c:
        c.execute(text(
            "UPDATE public.requirement_items SET citations_json = "
            "'[\"" + UDI_D + "\",\"https://example.gov/unknown\"]' WHERE id = 'r3'"
        ))
    _apply(engine)
    with engine.connect() as c:
        cites = c.execute(text("SELECT citations_json FROM public.requirement_items WHERE id='r3'")).scalar()
    assert "https://example.gov/unknown" in cites, cites
    assert "a7f1c3e2-0002" in cites, "the known URL should have been rewritten to its id"


def test_the_migration_is_idempotent(engine):
    _apply(engine)
    with engine.connect() as c:
        first = c.execute(text("SELECT count(*) FROM public.source_records")).scalar()
        r3_before = c.execute(text("SELECT citations_json FROM public.requirement_items WHERE id='r3'")).scalar()
    _apply(engine)
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM public.source_records")).scalar() == first
        assert c.execute(text("SELECT citations_json FROM public.requirement_items WHERE id='r3'")).scalar() == r3_before


def test_untargeted_rows_are_untouched(engine):
    """The migration deliberately fixes four requirements, not the whole table."""
    _apply(engine)
    with engine.connect() as c:
        assert c.execute(text(
            "SELECT citations_json FROM public.requirement_items WHERE id='rX'"
        )).scalar() == "[]"


def test_no_verification_status_was_promoted(engine):
    """This migration surfaces evidence. It makes no trust claim — that needs a human sign-off."""
    _apply(engine)
    with engine.connect() as c:
        statuses = {r[0] for r in c.execute(text(
            "SELECT DISTINCT verification_status FROM public.requirement_items"
        )).fetchall()}
    assert statuses == {"corpus_grounded"}, statuses
