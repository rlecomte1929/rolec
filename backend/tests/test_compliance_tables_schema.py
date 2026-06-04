"""BL-Compliance.1 — schema test for compliance_rules + compliance_alerts (AIQ-743).

Mirrors the two-mode pattern of test_rule_citations_schema.py:

  * **Static mode (always runs):** parses the migration SQL and asserts both
    tables, their columns, the severity / status CHECKs, the case_id and rule_id
    FKs with the correct ON DELETE actions, the indexes, and the SEC-002/003 RLS
    gate (ENABLE RLS + >=1 policy + REVOKE FROM anon) for each table. No DB
    credentials required — this is what CI exercises.

  * **Live mode (skipped unless RELOPASS_TEST_DB_URL is set):** connects to a
    real Postgres where the migration has been applied and verifies the tables,
    their columns, RLS state, zero anon grants, and FK rejection.
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

RULES_COLUMNS: Tuple[str, ...] = (
    "id",
    "category",
    "trigger_condition",
    "severity",
    "description",
    "active",
    "created_at",
    "updated_at",
)

ALERTS_COLUMNS: Tuple[str, ...] = (
    "id",
    "case_id",
    "rule_id",
    "status",
    "detail",
    "fired_at",
    "resolved_at",
    "created_at",
    "updated_at",
)

SEVERITY_VALUES: Tuple[str, ...] = ("low", "medium", "high", "critical")
STATUS_VALUES: Tuple[str, ...] = ("open", "resolved", "dismissed")

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20260607000000_compliance_rules_alerts.sql"
)


@pytest.fixture(scope="module")
def migration_sql() -> str:
    assert MIGRATION_PATH.exists(), (
        f"Migration file missing: {MIGRATION_PATH}. Did BL-Compliance.1 land?"
    )
    return MIGRATION_PATH.read_text()


def _create_table_body(sql: str, table: str) -> str:
    m = re.search(
        rf"create\s+table\s+(?:if\s+not\s+exists\s+)?public\.{table}\s*\((?P<body>.*?)\n\);",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    assert m, f"Could not find CREATE TABLE public.{table} block"
    return m.group("body")


@pytest.fixture(scope="module")
def rules_body(migration_sql: str) -> str:
    return _create_table_body(migration_sql, "compliance_rules")


@pytest.fixture(scope="module")
def alerts_body(migration_sql: str) -> str:
    return _create_table_body(migration_sql, "compliance_alerts")


# ─────────────────────────────────────────────────────────────────────────────
# Static-mode tests — run in every CI invocation, no DB required
# ─────────────────────────────────────────────────────────────────────────────


class TestMigrationStatic:
    def test_both_tables_present(self, migration_sql: str) -> None:
        for table in ("compliance_rules", "compliance_alerts"):
            assert re.search(
                rf"create\s+table\s+(?:if\s+not\s+exists\s+)?public\.{table}\b",
                migration_sql,
                re.IGNORECASE,
            ), f"Expected `create table public.{table}`"

    @pytest.mark.parametrize("column", RULES_COLUMNS)
    def test_rules_column_present(self, rules_body: str, column: str) -> None:
        assert re.search(rf"\b{column}\b", rules_body, re.IGNORECASE), (
            f"Column public.compliance_rules.{column} missing"
        )

    @pytest.mark.parametrize("column", ALERTS_COLUMNS)
    def test_alerts_column_present(self, alerts_body: str, column: str) -> None:
        assert re.search(rf"\b{column}\b", alerts_body, re.IGNORECASE), (
            f"Column public.compliance_alerts.{column} missing"
        )

    def test_severity_check_constraint(self, rules_body: str) -> None:
        m = re.search(
            r"severity\s+text\s+not\s+null[^,]*?check\s*\(\s*severity\s+in\s*\((?P<vals>.*?)\)\s*\)",
            rules_body,
            re.IGNORECASE | re.DOTALL,
        )
        assert m, "severity must have a CHECK (severity in (...)) constraint"
        for value in SEVERITY_VALUES:
            assert f"'{value}'" in m.group("vals"), (
                f"severity CHECK missing value {value!r}"
            )

    def test_status_check_constraint(self, alerts_body: str) -> None:
        m = re.search(
            r"status\s+text\s+not\s+null[^,]*?check\s*\(\s*status\s+in\s*\((?P<vals>.*?)\)\s*\)",
            alerts_body,
            re.IGNORECASE | re.DOTALL,
        )
        assert m, "status must have a CHECK (status in (...)) constraint"
        for value in STATUS_VALUES:
            assert f"'{value}'" in m.group("vals"), (
                f"status CHECK missing value {value!r}"
            )

    def test_case_id_fk_cascade(self, alerts_body: str) -> None:
        # Validation criterion: "FK to existing cases". Targets relocation_cases
        # (the populated case system the immigration data keys to), not the
        # near-empty public.cases.
        assert re.search(
            r"case_id\s+uuid\s+not\s+null\s+references\s+public\.relocation_cases\s*\(\s*id\s*\)"
            r"\s+on\s+delete\s+cascade",
            alerts_body,
            re.IGNORECASE,
        ), "case_id must FK public.relocation_cases(id) ON DELETE CASCADE"

    def test_rule_id_fk_restrict(self, alerts_body: str) -> None:
        assert re.search(
            r"rule_id\s+uuid\s+not\s+null\s+references\s+public\.compliance_rules"
            r"\s*\(\s*id\s*\)\s+on\s+delete\s+restrict",
            alerts_body,
            re.IGNORECASE,
        ), "rule_id must FK public.compliance_rules(id) ON DELETE RESTRICT"

    def test_alerts_indexes(self, migration_sql: str) -> None:
        for col in ("case_id", "rule_id"):
            assert re.search(
                rf"create\s+index\s+(?:if\s+not\s+exists\s+)?\w+\s+on\s+public\.compliance_alerts"
                rf"\s*\(\s*{col}\b",
                migration_sql,
                re.IGNORECASE,
            ), f"Index on public.compliance_alerts({col}) missing"

    @pytest.mark.parametrize("table", ("compliance_rules", "compliance_alerts"))
    def test_rls_gate(self, migration_sql: str, table: str) -> None:
        # CLAUDE.md hard gate: ENABLE RLS + >=1 policy + REVOKE FROM anon.
        assert re.search(
            rf"alter\s+table\s+public\.{table}\s+enable\s+row\s+level\s+security",
            migration_sql,
            re.IGNORECASE,
        ), f"Missing ENABLE ROW LEVEL SECURITY on {table}"
        assert re.search(
            rf"create\s+policy\s+\w+\s+on\s+public\.{table}",
            migration_sql,
            re.IGNORECASE,
        ), f"Missing CREATE POLICY on public.{table}"
        assert re.search(
            rf"revoke\s+all\s+on\s+public\.{table}\s+from\s+anon",
            migration_sql,
            re.IGNORECASE,
        ), f"Missing REVOKE ALL ON public.{table} FROM anon"


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
    @pytest.mark.parametrize(
        "table,columns",
        (("compliance_rules", RULES_COLUMNS), ("compliance_alerts", ALERTS_COLUMNS)),
    )
    def test_table_exists_with_columns(self, live_db_conn, table, columns) -> None:
        with live_db_conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=%s",
                (table,),
            )
            actual = {row[0] for row in cur.fetchall()}
        for col in columns:
            assert col in actual, f"public.{table}.{col} missing from live DB"

    @pytest.mark.parametrize("table", ("compliance_rules", "compliance_alerts"))
    def test_rls_and_zero_anon_grants(self, live_db_conn, table) -> None:
        with live_db_conn.cursor() as cur:
            cur.execute(
                "SELECT relrowsecurity FROM pg_class WHERE oid=%s::regclass",
                (f"public.{table}",),
            )
            assert cur.fetchone()[0] is True, f"RLS not enabled on {table}"
            cur.execute(
                "SELECT count(*) FROM pg_policies "
                "WHERE schemaname='public' AND tablename=%s",
                (table,),
            )
            assert cur.fetchone()[0] >= 1, f"No RLS policy present on {table}"
            cur.execute(
                "SELECT count(*) FROM information_schema.role_table_grants "
                "WHERE table_schema='public' AND table_name=%s AND grantee='anon'",
                (table,),
            )
            assert cur.fetchone()[0] == 0, f"anon must have zero grants on {table} (SEC-002)"

    def test_alert_fk_rejects_unknown_case(self, live_db_conn) -> None:
        import psycopg2  # type: ignore[import-not-found]

        with live_db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.compliance_rules (category, severity) "
                "VALUES ('test', 'low') RETURNING id"
            )
            rule_id = cur.fetchone()[0]
            with pytest.raises(psycopg2.errors.ForeignKeyViolation):
                cur.execute(
                    "INSERT INTO public.compliance_alerts (case_id, rule_id) "
                    "VALUES ('00000000-0000-0000-0000-000000000000', %s)",
                    (rule_id,),
                )
        live_db_conn.rollback()
