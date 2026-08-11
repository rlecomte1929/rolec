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
DROP TABLE IF EXISTS public.vendor_candidates CASCADE;
DROP TABLE IF EXISTS public.vendor_curation_runs CASCADE;
-- CASCADE: the promotion fixture below creates capability/scoring/accreditation tables that
-- FK onto suppliers, and they outlive a single test.
DROP TABLE IF EXISTS public.suppliers CASCADE;
CREATE TABLE public.suppliers (
  id varchar PRIMARY KEY, name varchar NOT NULL, legal_name varchar, status varchar NOT NULL,
  description text, website varchar, contact_email varchar, contact_phone varchar,
  languages_supported text, verified boolean NOT NULL DEFAULT false, vendor_id varchar,
  source text NOT NULL DEFAULT 'admin_manual'
    CHECK (source IN ('admin_manual','customer_upload','scraper_discovery','directory_import')),
  source_url text, source_reference text,
  created_at timestamp NOT NULL DEFAULT now(), updated_at timestamp NOT NULL DEFAULT now());
CREATE UNIQUE INDEX uq_suppliers_name_ci ON public.suppliers (lower(trim(name)));
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
    """The property that makes this safe to run twice by accident.

    This test used to assert `dup == 31` — it encoded the append-a-duplicate-set behaviour AS
    CORRECT, which is why the wart was dismissed as noise instead of fixed. It then happened
    in production. A second pass must now write nothing at all.
    """
    with engine.begin() as conn:
        stage(conn, candidates, dry_run=False)
    with engine.begin() as conn:
        results, _ = stage(conn, candidates, dry_run=False)
        pending, dup, _ = _counts(conn)

    assert sum(r.staged for r in results) == 0
    assert pending == 31, "the second run must not add a single new pending candidate"
    assert dup == 0, "nor a single duplicate row — re-staging is a no-op, not an append"


def test_a_supplier_we_already_have_stages_as_duplicate(engine, candidates):
    """Dedupe reaches across into the live directory, not just prior stagings."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO suppliers (id, name, website, status) "
                "VALUES (:i, :n, :w, 'active')"          # status is NOT NULL with no default
            ),
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


# ── promotion into the existing vetting queue ────────────────────────────────────────

SUPPLIER_SCHEMA = """
DROP TABLE IF EXISTS public.supplier_accreditations CASCADE;
DROP TABLE IF EXISTS public.supplier_scoring_metadata CASCADE;
DROP TABLE IF EXISTS public.supplier_service_capabilities CASCADE;
CREATE TABLE public.supplier_service_capabilities (
  id varchar PRIMARY KEY, supplier_id varchar NOT NULL REFERENCES public.suppliers(id) ON DELETE CASCADE,
  service_category varchar NOT NULL, coverage_scope_type varchar NOT NULL,
  country_code varchar, city_name varchar, specialization_tags text,
  min_budget numeric, max_budget numeric,
  family_support boolean NOT NULL, corporate_clients boolean NOT NULL, remote_support boolean NOT NULL,
  notes text, price_description text,
  platform_vetting_status text NOT NULL DEFAULT 'pending'
    CHECK (platform_vetting_status IN ('pending','approved','rejected','suspended')),
  vetted_by text, vetted_at timestamptz, vetting_notes text,
  created_at timestamp NOT NULL DEFAULT now(), updated_at timestamp NOT NULL DEFAULT now());
CREATE TABLE public.supplier_scoring_metadata (
  supplier_id varchar PRIMARY KEY REFERENCES public.suppliers(id) ON DELETE CASCADE,
  average_rating double precision, review_count integer NOT NULL DEFAULT 0,
  response_sla_hours integer, preferred_partner boolean NOT NULL DEFAULT false,
  premium_partner boolean NOT NULL DEFAULT false, last_verified_at timestamp,
  admin_score numeric, manual_priority integer,
  price_range_min_eur integer, price_range_max_eur integer, price_display text,
  created_at timestamp NOT NULL DEFAULT now(), updated_at timestamp NOT NULL DEFAULT now());
CREATE TABLE public.supplier_accreditations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  supplier_id varchar NOT NULL REFERENCES public.suppliers(id) ON DELETE CASCADE,
  body text NOT NULL, scheme text, membership_number text,
  status text NOT NULL DEFAULT 'claimed'
    CHECK (status IN ('claimed','verified','expired','revoked','not_found')),
  valid_from date, valid_until date, evidence_url text,
  verification_method text CHECK (verification_method IS NULL OR verification_method IN
    ('public_registry','supplier_document','manual_email','directory_listing')),
  verified_by text, verified_at timestamptz, notes text,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT sa_verified_needs_evidence
    CHECK (status <> 'verified' OR (evidence_url IS NOT NULL AND verified_at IS NOT NULL)));
CREATE UNIQUE INDEX supplier_accreditations_unique_claim
  ON public.supplier_accreditations (supplier_id, body, COALESCE(scheme, ''));
"""


@pytest.fixture
def full_engine(engine):
    """The staging schema plus the live directory tables promotion writes to."""
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute(SUPPLIER_SCHEMA)
        raw.commit()
    finally:
        raw.close()
    return engine


def _session(engine):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine)()


def _staged(engine, candidates):
    with engine.begin() as conn:
        stage(conn, candidates, dry_run=False)


def test_promotion_dry_run_writes_no_supplier(full_engine, candidates):
    from backend.imports.suppliers.executor import promote

    _staged(full_engine, candidates)
    with _session(full_engine) as session:
        n, _, _ = promote(session, dry_run=True)
        assert n == 31
    with full_engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM suppliers")).scalar_one() == 0


def test_promotion_lands_everything_unvetted(full_engine, candidates):
    from backend.imports.suppliers.executor import promote

    _staged(full_engine, candidates)
    with _session(full_engine) as session:
        promoted, _, _ = promote(session, dry_run=False)

    assert promoted == 31, "every candidate is accounted for, merged or new"
    with full_engine.begin() as conn:
        pending, approved = conn.execute(
            text(
                "SELECT count(*) FILTER (WHERE platform_vetting_status='pending'), "
                "       count(*) FILTER (WHERE platform_vetting_status='approved') "
                "FROM supplier_service_capabilities"
            )
        ).one()
    assert (pending, approved) == (31, 0), "nothing may arrive pre-approved"


def test_a_company_in_two_corridors_is_one_supplier_with_two_capabilities(
    full_engine, candidates
):
    """Two companies in this harvest serve both corridors, and each must be ONE supplier with
    TWO capabilities. Dropping the second would silently lose that corridor's coverage.

    - Grospiron International — identical name in both rows.
    - AGS France — written 'AGS France (SOFDI – Société Française de Déménagement
      International)' for FR-DE and 'AGS France (SOFDI)' for FR-NO. Same FIDI affiliate, two
      spellings, which is why `_name_key` drops parenthetical asides.

    So 31 candidates become 29 suppliers and 31 capabilities."""
    from backend.imports.suppliers.executor import promote

    _staged(full_engine, candidates)
    with _session(full_engine) as session:
        promote(session, dry_run=False)

    with full_engine.begin() as conn:
        suppliers, caps = conn.execute(
            text("SELECT (SELECT count(*) FROM suppliers), "
                 "       (SELECT count(*) FROM supplier_service_capabilities)")
        ).one()
        grospiron = conn.execute(
            text(
                "SELECT count(*) FROM supplier_service_capabilities c "
                "JOIN suppliers s ON s.id = c.supplier_id "
                "WHERE s.name = 'Grospiron International'"
            )
        ).scalar_one()

    assert (suppliers, caps) == (29, 31)
    assert grospiron == 2

    with full_engine.begin() as conn:
        ags = conn.execute(
            text(
                "SELECT count(*) FROM supplier_service_capabilities c "
                "JOIN suppliers s ON s.id = c.supplier_id "
                "WHERE s.name LIKE 'AGS France%'"
            )
        ).scalar_one()
    assert ags == 2, "the two spellings of AGS France must resolve to one supplier"


def test_the_registry_evidence_survives_promotion(full_engine, candidates):
    """Without this the promoted supplier is indistinguishable from a scrape."""
    from backend.imports.suppliers.executor import promote

    _staged(full_engine, candidates)
    with _session(full_engine) as session:
        promote(session, dry_run=False)

    with full_engine.begin() as conn:
        total, no_evidence, verified = conn.execute(
            text(
                "SELECT count(*), count(*) FILTER (WHERE evidence_url IS NULL), "
                "       count(*) FILTER (WHERE status='verified') "
                "FROM supplier_accreditations"
            )
        ).one()

    # 29, not 31: the unique claim index is (supplier_id, body, scheme), so a company in two
    # corridors evidenced by the same registry holds ONE accreditation, not two.
    assert total == 29
    assert no_evidence == 0
    assert verified == 0, "a registry listing is 'claimed'; the human who approves verifies it"


def test_promotion_is_idempotent(full_engine, candidates):
    from backend.imports.suppliers.executor import promote

    _staged(full_engine, candidates)
    with _session(full_engine) as session:
        promote(session, dry_run=False)
    with _session(full_engine) as session:
        again, _, _ = promote(session, dry_run=False)

    assert again == 0
    with full_engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM suppliers")).scalar_one() == 29


def test_every_candidate_is_linked_to_its_supplier(full_engine, candidates):
    from backend.imports.suppliers.executor import promote

    _staged(full_engine, candidates)
    with _session(full_engine) as session:
        promote(session, dry_run=False)

    with full_engine.begin() as conn:
        unlinked = conn.execute(
            text(
                "SELECT count(*) FROM vendor_candidates "
                "WHERE status IN ('pending','duplicate') AND promoted_supplier_id IS NULL"
            )
        ).scalar_one()
    assert unlinked == 0


def test_a_harvest_matches_an_existing_supplier_by_LEGAL_name(full_engine, candidates):
    """The Expat Relocation case, verified against production before it was coded.

    Prod holds supplier `no-leg-1` named "Expat Relocation Norway" with
    `legal_name = "Expat Relocation AS"`. The harvest sources from the EuRA register, which
    reports the legal entity — so it found "Expat Relocation AS", character for character.

    Matching only on `name` scores those two at 0.83 similarity and imports a duplicate of a
    company we already have. Matching on `legal_name` too makes it a capability instead.
    """
    from backend.imports.suppliers.executor import promote

    with full_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO suppliers (id, name, legal_name, status) "
                "VALUES ('no-leg-1', 'Expat Relocation Norway', 'Expat Relocation AS', 'active')"
            )
        )
    _staged(full_engine, candidates)
    with _session(full_engine) as session:
        promote(session, dry_run=False)

    with full_engine.begin() as conn:
        rows = conn.execute(
            text("SELECT count(*) FROM suppliers WHERE name LIKE 'Expat Relocation%'")
        ).scalar_one()
        attached = conn.execute(
            text(
                "SELECT count(*) FROM supplier_service_capabilities "
                "WHERE supplier_id = 'no-leg-1'"
            )
        ).scalar_one()

    assert rows == 1, "no second Expat Relocation row may be created"
    assert attached == 1, "the FR-NO housing capability attaches to the supplier we already had"


def test_staging_twice_writes_nothing_the_second_time(full_engine, candidates):
    """The bug that hit production on 2026-08-11.

    `--promote` implies `--apply`, so the natural "stage, check the numbers, then promote"
    sequence runs staging twice. Every row matched the first run's dedupe keys, so the second
    pass re-staged all 31 as 'duplicate' under 8 fresh runs — 62 candidates and 16 runs where
    there should have been 31 and 8. The directory was unharmed (the supplier name index and
    add_capability's duplicate check absorbed it) but the staging tables needed hand cleanup.

    Staging must be a no-op on a file it has already ingested.
    """
    _staged(full_engine, candidates)
    with full_engine.begin() as conn:
        first = conn.execute(
            text("SELECT (SELECT count(*) FROM vendor_candidates), "
                 "       (SELECT count(*) FROM vendor_curation_runs)")
        ).one()

    _staged(full_engine, candidates)                      # exactly what the CLI did
    with full_engine.begin() as conn:
        second = conn.execute(
            text("SELECT (SELECT count(*) FROM vendor_candidates), "
                 "       (SELECT count(*) FROM vendor_curation_runs)")
        ).one()

    assert first == (31, 8)
    assert second == first, (
        f"re-staging appended rows: {first} became {second}. A second pass over the same file "
        "must write nothing."
    )


def test_a_genuinely_new_row_still_stages_after_a_first_run(full_engine, candidates):
    """The skip must not wedge the table shut — a later harvest with a new company still lands."""
    from backend.app.services.registry_sources import SOURCES
    from backend.app.services.vendor_harvester import Candidate

    _staged(full_engine, candidates)
    fidi = next(s for s in SOURCES if s.name == "FIDI FAIM member directory")
    newcomer = Candidate(
        name="Brand New Movers GmbH", website_url="", corridor="FR-DE",
        service_category="movers", source=fidi,
        source_url="https://www.fidi.org/find-fidi-affiliate/brand-new-movers",
        accreditation_body="FIDI", country_code="DE",
    )
    _staged(full_engine, list(candidates) + [newcomer])

    with full_engine.begin() as conn:
        total = conn.execute(text("SELECT count(*) FROM vendor_candidates")).scalar_one()
        landed = conn.execute(
            text("SELECT count(*) FROM vendor_candidates WHERE name = 'Brand New Movers GmbH'")
        ).scalar_one()
    assert (total, landed) == (32, 1)
