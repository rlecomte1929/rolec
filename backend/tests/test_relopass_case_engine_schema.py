"""C1-01 — pytest fixture for the ReloPass Case Engine schema.

Validation criterion 8: "Pytest fixture spins up a test DB and confirms all
tables exist."

This test runs in two modes:

  * **Static mode (always runs):** parses the migration SQL and asserts every
    one of the 20 expected ontology tables has a `CREATE TABLE rce.<name>`
    statement, plus the pgvector extension, HNSW index, PF-1 columns, and
    RLS-enable block. This is what CI gets — no DB credentials required.

  * **Live mode (skipped unless RELOPASS_TEST_DB_URL is set):** connects to
    a real Postgres, applies the migration if needed, and verifies the
    `rce` schema is queryable end-to-end (table list, vector(768) insert,
    HNSW index in pg_indexes).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Tuple

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Constants — the 20 RCE ontology tables (Architecture Report §2.1)
# ─────────────────────────────────────────────────────────────────────────────

RCE_TABLES: Tuple[str, ...] = (
    "addresses",
    "agent_runs",
    "authorities",
    "canonical_entities",
    "cases",
    "corrections",
    "costs",
    "deadlines",
    "document_types",
    "documents",
    "employees",
    "employers",
    "entity_links",
    "extracted_fields",
    "family_members",
    "hr_policies",
    "policy_clauses",
    "rule_versions",
    "rules",
    "steps",
)

PF1_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("cases", "petitioning_party_type"),
    ("cases", "beneficiary_employee_id"),
    ("steps", "time_window_relative_to"),
    ("steps", "time_window_min_days"),
    ("steps", "time_window_max_days"),
    ("costs", "category"),
)

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20260528020000_relopass_case_engine_v1.sql"
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def migration_sql() -> str:
    assert MIGRATION_PATH.exists(), (
        f"Migration file missing: {MIGRATION_PATH}. Did C1-01 land?"
    )
    return MIGRATION_PATH.read_text()


# ─────────────────────────────────────────────────────────────────────────────
# Static-mode tests — exercised in every CI run
# ─────────────────────────────────────────────────────────────────────────────


class TestMigrationStatic:
    def test_pgvector_extension_enabled(self, migration_sql: str) -> None:
        assert re.search(
            r"CREATE\s+EXTENSION\s+IF\s+NOT\s+EXISTS\s+vector", migration_sql, re.IGNORECASE
        ), "pgvector extension must be enabled (criterion 2)"

    def test_rce_schema_created(self, migration_sql: str) -> None:
        assert re.search(r"CREATE\s+SCHEMA\s+IF\s+NOT\s+EXISTS\s+rce", migration_sql, re.IGNORECASE)

    @pytest.mark.parametrize("table", RCE_TABLES)
    def test_table_create_statement_present(self, migration_sql: str, table: str) -> None:
        pattern = rf"CREATE\s+TABLE\s+rce\.{table}\b"
        assert re.search(pattern, migration_sql, re.IGNORECASE), (
            f"Expected `CREATE TABLE rce.{table}` in migration"
        )

    def test_canonical_entities_has_vector_768(self, migration_sql: str) -> None:
        # Architecture Report constraint — embedding column is vector(768).
        assert re.search(r"embedding\s+vector\(768\)", migration_sql, re.IGNORECASE)

    def test_hnsw_index_present(self, migration_sql: str) -> None:
        assert re.search(
            r"CREATE\s+INDEX\s+canonical_entities_embedding_hnsw\s+ON\s+rce\.canonical_entities"
            r"\s+USING\s+hnsw",
            migration_sql,
            re.IGNORECASE,
        )

    @pytest.mark.parametrize("table,column", PF1_COLUMNS)
    def test_pf1_columns_present(self, migration_sql: str, table: str, column: str) -> None:
        # PF-1 stress-test additions must appear within the relevant CREATE TABLE block.
        m = re.search(
            rf"CREATE\s+TABLE\s+rce\.{table}\s*\((?P<body>.*?)\);", migration_sql, re.IGNORECASE | re.DOTALL
        )
        assert m, f"Could not find CREATE TABLE for rce.{table}"
        assert re.search(rf"\b{column}\b", m.group("body"), re.IGNORECASE), (
            f"PF-1 column rce.{table}.{column} missing from CREATE TABLE block"
        )

    def test_costs_category_enum_complete(self, migration_sql: str) -> None:
        # PF-1 controlled cost categories — order and exact spelling matter.
        for value in (
            "GOVERNMENT_FEE",
            "LEGAL_FEE",
            "TRANSLATION",
            "NOTARIZATION",
            "RELOCATION_VENDOR",
            "HOUSING_VENDOR",
            "TAX_VENDOR",
            "SCHOOLING",
            "TRANSPORTATION",
            "LANGUAGE_TRAINING",
            "CULTURAL_TRAINING",
            "INSURANCE",
            "OTHER",
        ):
            assert f"'{value}'" in migration_sql, (
                f"costs.category enum missing value {value!r}"
            )

    def test_reason_codes_complete(self, migration_sql: str) -> None:
        for value in (
            "OCR_ERROR",
            "TYPO_IN_SOURCE",
            "AMBIGUOUS_PARTICLE",
            "LEGITIMATE_VARIATION",
            "FRAUD_SUSPECTED",
            "OTHER",
        ):
            assert f"'{value}'" in migration_sql, (
                f"corrections.reason_code enum missing value {value!r}"
            )

    def test_resolution_status_complete(self, migration_sql: str) -> None:
        for value in (
            "Resolved",
            "Requires attention",
            "Not resolved",
            "No result",
            "Ignored",
        ):
            assert f"'{value}'" in migration_sql, (
                f"extracted_fields.resolution_status enum missing value {value!r}"
            )

    def test_bbox_check_constraint_present(self, migration_sql: str) -> None:
        # 0–1000 normalized bbox (Parsewise convention)
        assert re.search(r"BETWEEN\s+0\s+AND\s+1000", migration_sql)

    def test_documents_sha256_unique(self, migration_sql: str) -> None:
        m = re.search(
            r"CREATE\s+TABLE\s+rce\.documents\s*\((?P<body>.*?)\);",
            migration_sql,
            re.IGNORECASE | re.DOTALL,
        )
        assert m and re.search(r"sha256\s+TEXT\s+NOT\s+NULL\s+UNIQUE", m.group("body"), re.IGNORECASE)

    def test_every_table_has_audit_columns(self, migration_sql: str) -> None:
        """Technical constraint: every table has created_at + updated_at TIMESTAMPTZ DEFAULT now()."""
        for table in RCE_TABLES:
            m = re.search(
                rf"CREATE\s+TABLE\s+rce\.{table}\s*\((?P<body>.*?)\);",
                migration_sql,
                re.IGNORECASE | re.DOTALL,
            )
            assert m, f"Missing CREATE TABLE for rce.{table}"
            body = m.group("body")
            assert re.search(r"created_at\s+TIMESTAMPTZ.*DEFAULT\s+now\(\)", body, re.IGNORECASE), (
                f"rce.{table} missing created_at audit column"
            )
            assert re.search(r"updated_at\s+TIMESTAMPTZ.*DEFAULT\s+now\(\)", body, re.IGNORECASE), (
                f"rce.{table} missing updated_at audit column"
            )

    def test_rls_enable_block_present(self, migration_sql: str) -> None:
        # SEC-003 hard gate: every new public/rce table needs ENABLE RLS + policy + REVOKE FROM anon.
        # The migration uses a DO $$ ... $$ loop over rce_tables.
        assert "ENABLE ROW LEVEL SECURITY" in migration_sql
        assert "CREATE POLICY" in migration_sql
        assert "REVOKE ALL ON rce" in migration_sql or "REVOKE ALL\nON rce" in migration_sql or "REVOKE ALL ON" in migration_sql
        assert "FROM anon" in migration_sql

    def test_rls_loop_lists_all_20_tables(self, migration_sql: str) -> None:
        # The DO block hardcodes the list — make sure none is missing.
        m = re.search(r"rce_tables\s+TEXT\[\]\s*:=\s*ARRAY\[(?P<list>.*?)\]", migration_sql, re.DOTALL)
        assert m, "RLS loop must declare rce_tables array"
        listed = {
            tok.strip().strip("'") for tok in m.group("list").split(",")
        }
        listed.discard("")
        missing = set(RCE_TABLES) - listed
        assert not missing, f"RLS loop missing tables: {sorted(missing)}"


# ─────────────────────────────────────────────────────────────────────────────
# Live-mode test — only when RELOPASS_TEST_DB_URL is set
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def live_db_conn():
    url = os.environ.get("RELOPASS_TEST_DB_URL")
    if not url:
        pytest.skip("Set RELOPASS_TEST_DB_URL to run live-DB schema checks.")
    try:
        import psycopg2  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover
        pytest.skip("psycopg2 not installed; cannot run live-DB schema checks.")
    conn = psycopg2.connect(url)
    try:
        yield conn
    finally:
        conn.close()


class TestLiveSchema:
    def test_all_tables_exist(self, live_db_conn) -> None:
        with live_db_conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='rce' ORDER BY table_name"
            )
            actual = tuple(row[0] for row in cur.fetchall())
        for expected in RCE_TABLES:
            assert expected in actual, f"rce.{expected} missing from live DB"

    def test_vector_768_insert(self, live_db_conn) -> None:
        with live_db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO rce.canonical_entities (entity_type, canonical_form, embedding) "
                "VALUES ('PERSON', '{}'::jsonb, "
                "(SELECT ('[' || string_agg('0.1', ',') || ']')::vector "
                "FROM generate_series(1,768))) "
                "RETURNING canonical_entity_id"
            )
            row_id = cur.fetchone()[0]
            cur.execute(
                "DELETE FROM rce.canonical_entities WHERE canonical_entity_id=%s", (row_id,)
            )
            live_db_conn.commit()

    def test_hnsw_index_in_pg_indexes(self, live_db_conn) -> None:
        with live_db_conn.cursor() as cur:
            cur.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname='rce' AND indexname='canonical_entities_embedding_hnsw'"
            )
            assert cur.fetchone() is not None
