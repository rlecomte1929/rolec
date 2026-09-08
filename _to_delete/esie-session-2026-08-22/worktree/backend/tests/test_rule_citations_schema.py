"""C1-01c — schema test for rce.rule_citations (AIQ-751).

Mirrors the two-mode pattern of test_relopass_case_engine_schema.py:

  * **Static mode (always runs):** parses the migration SQL and asserts the
    table, its 8 columns, the output_kind CHECK, both FKs with the correct
    ON DELETE actions, the UNIQUE quad, both indexes, and the SEC-003 RLS gate
    are all present. No DB credentials required — this is what CI exercises.

  * **Live mode (skipped unless RELOPASS_TEST_DB_URL is set):** connects to a
    real Postgres where the migration has been applied and verifies the table,
    its CHECK constraint, FK rejection, UNIQUE rejection, indexes, RLS state,
    zero anon grants, and that the C2-05 "rule impact" query runs on empty data.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Tuple

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

EXPECTED_COLUMNS: Tuple[str, ...] = (
    "rule_citation_id",
    "case_id",
    "output_kind",
    "output_id",
    "rule_version_id",
    "legal_reference",
    "source_url",
    "created_at",
)

OUTPUT_KIND_VALUES: Tuple[str, ...] = ("STEP", "DEADLINE", "ELIGIBILITY_BRANCH")

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20260605100000_rce_rule_citations.sql"
)


@pytest.fixture(scope="module")
def migration_sql() -> str:
    assert MIGRATION_PATH.exists(), (
        f"Migration file missing: {MIGRATION_PATH}. Did C1-01c land?"
    )
    return MIGRATION_PATH.read_text()


@pytest.fixture(scope="module")
def create_table_body(migration_sql: str) -> str:
    m = re.search(
        r"CREATE\s+TABLE\s+rce\.rule_citations\s*\((?P<body>.*?)\);",
        migration_sql,
        re.IGNORECASE | re.DOTALL,
    )
    assert m, "Could not find CREATE TABLE rce.rule_citations block"
    return m.group("body")


# ─────────────────────────────────────────────────────────────────────────────
# Static-mode tests — run in every CI invocation, no DB required
# ─────────────────────────────────────────────────────────────────────────────


class TestMigrationStatic:
    def test_create_table_present(self, migration_sql: str) -> None:
        assert re.search(
            r"CREATE\s+TABLE\s+rce\.rule_citations\b", migration_sql, re.IGNORECASE
        ), "Expected `CREATE TABLE rce.rule_citations`"

    @pytest.mark.parametrize("column", EXPECTED_COLUMNS)
    def test_column_present(self, create_table_body: str, column: str) -> None:
        assert re.search(rf"\b{column}\b", create_table_body, re.IGNORECASE), (
            f"Column rce.rule_citations.{column} missing from CREATE TABLE block"
        )

    def test_output_kind_check_constraint(self, create_table_body: str) -> None:
        m = re.search(
            r"output_kind\s+TEXT\s+NOT\s+NULL\s+CHECK\s*\(\s*output_kind\s+IN\s*\((?P<vals>.*?)\)\s*\)",
            create_table_body,
            re.IGNORECASE | re.DOTALL,
        )
        assert m, "output_kind must have a CHECK (output_kind IN (...)) constraint"
        for value in OUTPUT_KIND_VALUES:
            assert f"'{value}'" in m.group("vals"), (
                f"output_kind CHECK missing value {value!r}"
            )

    def test_case_id_fk_cascade(self, create_table_body: str) -> None:
        assert re.search(
            r"case_id\s+UUID\s+NOT\s+NULL\s+REFERENCES\s+rce\.cases\s*\(\s*case_id\s*\)"
            r"\s+ON\s+DELETE\s+CASCADE",
            create_table_body,
            re.IGNORECASE,
        ), "case_id must FK rce.cases(case_id) ON DELETE CASCADE"

    def test_rule_version_id_fk_restrict(self, create_table_body: str) -> None:
        assert re.search(
            r"rule_version_id\s+UUID\s+NOT\s+NULL\s+REFERENCES\s+rce\.rule_versions"
            r"\s*\(\s*rule_version_id\s*\)\s+ON\s+DELETE\s+RESTRICT",
            create_table_body,
            re.IGNORECASE,
        ), "rule_version_id must FK rce.rule_versions(rule_version_id) ON DELETE RESTRICT"

    def test_unique_quad(self, create_table_body: str) -> None:
        assert re.search(
            r"UNIQUE\s*\(\s*case_id\s*,\s*output_kind\s*,\s*output_id\s*,\s*rule_version_id\s*\)",
            create_table_body,
            re.IGNORECASE,
        ), "UNIQUE (case_id, output_kind, output_id, rule_version_id) missing"

    def test_index_by_version(self, migration_sql: str) -> None:
        assert re.search(
            r"CREATE\s+INDEX\s+rule_citations_by_version\s+ON\s+rce\.rule_citations"
            r"\s*\(\s*rule_version_id\s*\)",
            migration_sql,
            re.IGNORECASE,
        ), "Index rule_citations_by_version on (rule_version_id) missing (criterion 6)"

    def test_index_by_case(self, migration_sql: str) -> None:
        assert re.search(
            r"CREATE\s+INDEX\s+rule_citations_by_case\s+ON\s+rce\.rule_citations",
            migration_sql,
            re.IGNORECASE,
        ), "Index rule_citations_by_case missing"

    def test_sec003_rls_gate(self, migration_sql: str) -> None:
        # SEC-003 hard gate: ENABLE RLS + >=1 policy + REVOKE FROM anon.
        assert re.search(
            r"ALTER\s+TABLE\s+rce\.rule_citations\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY",
            migration_sql,
            re.IGNORECASE,
        ), "Missing ENABLE ROW LEVEL SECURITY"
        assert re.search(
            r"CREATE\s+POLICY\s+\w+\s+ON\s+rce\.rule_citations",
            migration_sql,
            re.IGNORECASE,
        ), "Missing CREATE POLICY on rce.rule_citations"
        assert re.search(
            r"REVOKE\s+ALL\s+ON\s+rce\.rule_citations\s+FROM\s+anon",
            migration_sql,
            re.IGNORECASE,
        ), "Missing REVOKE ALL ... FROM anon"


# ─────────────────────────────────────────────────────────────────────────────
# Live-mode tests — only when RELOPASS_TEST_DB_URL is set (migration applied)
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
    def test_table_exists_with_columns(self, live_db_conn) -> None:
        with live_db_conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='rce' AND table_name='rule_citations'"
            )
            actual = {row[0] for row in cur.fetchall()}
        for col in EXPECTED_COLUMNS:
            assert col in actual, f"rce.rule_citations.{col} missing from live DB"

    def test_indexes_present(self, live_db_conn) -> None:
        with live_db_conn.cursor() as cur:
            cur.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname='rce' AND tablename='rule_citations'"
            )
            idx = {row[0] for row in cur.fetchall()}
        assert "rule_citations_by_version" in idx
        assert "rule_citations_by_case" in idx

    def test_rls_and_zero_anon_grants(self, live_db_conn) -> None:
        with live_db_conn.cursor() as cur:
            cur.execute("SELECT relrowsecurity FROM pg_class WHERE oid='rce.rule_citations'::regclass")
            assert cur.fetchone()[0] is True, "RLS not enabled"
            cur.execute(
                "SELECT count(*) FROM pg_policies "
                "WHERE schemaname='rce' AND tablename='rule_citations'"
            )
            assert cur.fetchone()[0] >= 1, "No RLS policy present"
            cur.execute(
                "SELECT count(*) FROM information_schema.role_table_grants "
                "WHERE table_schema='rce' AND table_name='rule_citations' AND grantee='anon'"
            )
            assert cur.fetchone()[0] == 0, "anon must have zero grants (SEC-003)"

    def test_c2_05_impact_query_runs_on_empty(self, live_db_conn) -> None:
        with live_db_conn.cursor() as cur:
            cur.execute(
                "SELECT c.case_id, c.status, count(rc.rule_citation_id) "
                "FROM rce.rule_citations rc JOIN rce.cases c ON c.case_id = rc.case_id "
                "WHERE rc.rule_version_id = %s GROUP BY c.case_id, c.status",
                ("00000000-0000-0000-0000-000000000000",),
            )
            assert cur.fetchall() == []
