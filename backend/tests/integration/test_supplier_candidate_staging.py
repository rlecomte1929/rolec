"""[AIQ-1788] The harvest actually lands in vendor_candidates, against real Postgres.

The planning half (`plan_pair`) is pure and covered by unit tests. This covers the half that
touches the database, which is where the interesting failures live: a `date` column fed a bare
year, a jsonb column fed a Python list, an `existing_dedupe_keys` that could not execute at all
on SQLAlchemy 2. None of those are visible without a real server.

Runs the real CLI path end to end on the real 38-row harvest. `integration`-marked, so CI's
`-m "not integration"` run skips it.

    docker run -d --name candpg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=candtest \
      -p 55435:5432 postgres:15-alpine

    DATABASE_URL=postgresql://postgres:test@127.0.0.1:55435/candtest \
      pytest backend/tests/integration/test_supplier_candidate_staging.py -v
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, text  # noqa: E402

from backend.imports.suppliers.executor import stage  # noqa: E402
from backend.imports.suppliers.parsers import read_csv  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "")
_IS_PG = DATABASE_URL.startswith("postgres")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _IS_PG,
        reason="needs a Postgres DATABASE_URL — the date/jsonb casts and the dedupe read "
        "are exactly what a mock cannot check.",
    ),
]

REPO = Path(__file__).resolve().parents[3]
HARVEST = REPO / "audos-workspace-776786" / "data" / "card-c-harvest.csv"

#: Mirrors the prod columns verified 2026-08-11 (migrations 20260719210834 + 20260805214336).
SCHEMA = """
DROP TABLE IF EXISTS public.vendor_candidates;
DROP TABLE IF EXISTS public.vendor_curation_runs;
DROP TABLE IF EXISTS public.suppliers;
CREATE TABLE public.suppliers (
  id varchar PRIMARY KEY, name varchar NOT NULL, website varchar NULL,
  status varchar NOT NULL DEFAULT 'active', verified boolean NOT NULL DEFAULT false);
CREATE TABLE public.vendor_curation_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  corridor text NOT NULL, service_category text NOT NULL,
  run_date timestamptz NOT NULL DEFAULT now(),
  sources_searched jsonb NOT NULL DEFAULT '[]',
  candidates_found integer NOT NULL DEFAULT 0, promoted_count integer NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued','searching','staged','reviewed','completed','failed')),
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE public.vendor_candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid REFERENCES public.vendor_curation_runs(id) ON DELETE SET NULL,
  name text NOT NULL, website_url text, email text, city text, country_code text,
  service_category text NOT NULL, source_url text, source_name text,
  source_tier integer CHECK (source_tier BETWEEN 1 AND 3),
  confidence_score numeric(3,2) CHECK (confidence_score BETWEEN 0 AND 1),
  bar_registered boolean, notes text,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','approved','rejected','duplicate','needs_reverification')),
  promoted_supplier_id text, reviewed_by text, reviewed_at timestamptz,
  accreditation_body text, accreditation_number text, accreditation_expiry date,
  legal_name text, vat_number text, corridor text, phone text, dedupe_key text,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
"""


@pytest.fixture
def engine():
    eng = create_engine(DATABASE_URL, future=True)
    raw = eng.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        cur.execute(SCHEMA)
        raw.commit()
    finally:
        raw.close()
    yield eng
    eng.dispose()


@pytest.fixture
def candidates():
    return list(read_csv(HARVEST))


def _counts(conn):
    return conn.execute(
        text(
            "SELECT count(*) FILTER (WHERE status='pending'), "
            "       count(*) FILTER (WHERE status='duplicate'), "
            "       (SELECT count(*) FROM vendor_curation_runs) "
            "FROM vendor_candidates"
        )
    ).one()


def test_a_dry_run_writes_nothing(engine, candidates):
    """A preview that took a different code path would not be a preview."""
    with engine.begin() as conn:
        results, rejections = stage(conn, candidates, dry_run=True)
        assert sum(r.staged for r in results) == 31
        assert len(rejections) == 7
        assert _counts(conn) == (0, 0, 0)


def test_apply_stages_31_pending_and_rejects_7(engine, candidates):
    with engine.begin() as conn:
        results, rejections = stage(conn, candidates, dry_run=False)
        pending, dup, runs = _counts(conn)

    assert (pending, dup) == (31, 0)
    assert len(rejections) == 7
    assert runs == 8, (
        "one of the nine pairs has every row rejected, so it must open no run at all — "
        "an empty run would read as 'searched, found nothing'"
    )
    assert all(r.run_id for r in results if r.staged)


def test_a_bare_year_expiry_survives_the_date_column(engine, candidates):
    """'2028' in the CSV must reach Postgres as 2028-01-01, not blow up the insert."""
    with engine.begin() as conn:
        stage(conn, candidates, dry_run=False)
        row = conn.execute(
            text(
                "SELECT accreditation_expiry FROM vendor_candidates "
                "WHERE name LIKE 'AGS France%' AND corridor = 'FR-DE'"
            )
        ).scalar_one()
    assert str(row) == "2028-01-01"


def test_rerunning_stages_nothing_new(engine, candidates):
    """The property that makes this safe to run twice by accident."""
    with engine.begin() as conn:
        stage(conn, candidates, dry_run=False)
    with engine.begin() as conn:
        results, _ = stage(conn, candidates, dry_run=False)
        pending, dup, _ = _counts(conn)

    assert sum(r.staged for r in results) == 0
    assert pending == 31, "the second run must not add a single new pending candidate"
    assert dup == 31


def test_a_supplier_we_already_have_stages_as_duplicate(engine, candidates):
    """Dedupe reaches across into the live directory, not just prior stagings."""
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO suppliers (id, name, website) VALUES (:i, :n, :w)"),
            {"i": "de-mv-1", "n": "Grospiron International", "w": None},
        )
    with engine.begin() as conn:
        stage(conn, candidates, dry_run=False)
        status = conn.execute(
            text(
                "SELECT status FROM vendor_candidates "
                "WHERE name = 'Grospiron International' AND corridor = 'FR-DE'"
            )
        ).scalar_one()
    assert status == "duplicate", (
        "matched by the name fallback — this supplier row has no website, and neither does "
        "the harvest row, so the domain key cannot help"
    )


def test_nothing_reaches_the_live_directory(engine, candidates):
    """The whole safety model: staging writes two tables and never suppliers."""
    with engine.begin() as conn:
        stage(conn, candidates, dry_run=False)
        assert conn.execute(text("SELECT count(*) FROM suppliers")).scalar_one() == 0


def test_every_staged_row_keeps_its_evidence_and_provenance(engine, candidates):
    with engine.begin() as conn:
        stage(conn, candidates, dry_run=False)
        bad = conn.execute(
            text(
                "SELECT count(*) FROM vendor_candidates "
                "WHERE source_url IS NULL OR source_name IS NULL "
                "   OR source_tier IS NULL OR dedupe_key IS NULL"
            )
        ).scalar_one()
    assert bad == 0, "a candidate with no evidence URL is indistinguishable from a scrape"
