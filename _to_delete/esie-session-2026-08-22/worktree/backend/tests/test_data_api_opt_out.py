"""FRIDAY-003b — verification test for the Data API opt-out migration (AIQ-763).

Mirrors the two-mode pattern of test_rule_citations_schema.py:

  * **Static mode (always runs):** parses the migration SQL and asserts every
    one of the 24 high-confidence REVOKE statements is present, that the 5
    VERIFY tables are NOT touched (deferred), and that none of the 6 KEEP
    tables are revoked. No DB credentials required — this is what CI exercises.

  * **Live mode (skipped unless RELOPASS_TEST_DB_URL is set):** connects to a
    real Postgres where the migration has been applied and verifies the 8
    anon-revoke tables have zero anon grants, the 16 authenticated-revoke
    tables have zero authenticated grants, and the KEEP tables retain grants.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Tuple

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Constants — the audit's classification (backend/docs/data-api-audit.md §6)
# ─────────────────────────────────────────────────────────────────────────────

# anon grants to revoke (6a + 6b)
ANON_REVOKE_TABLES: Tuple[str, ...] = (
    "ai_spend_requests",
    "rp_debug_kv",
    "country_events",
    "country_profiles",
    "country_resource_items",
    "country_resource_sections",
    "requirement_items",
    "requirements_catalog",
)

# authenticated grants to revoke (6c)
AUTHENTICATED_REVOKE_TABLES: Tuple[str, ...] = (
    "agent_runs",
    "ai_human_feedback",
    "ai_model_energy_profiles",
    "bamboohr_sync_log",
    "personio_sync_log",
    "conjoint_responses",
    "conjoint_results",
    "conjoint_studies",
    "default_policy_templates",
    "ocr_shadow_comparisons",
    "prompt_routing",
    "prompt_versions",
    "translation_cache",
    "readiness_templates",
    "readiness_template_milestones",
    "readiness_template_checklist_items",
)

# Deliberately retained (must NOT be revoked by this migration)
KEEP_TABLES: Tuple[str, ...] = (
    "feedback",
    "error_tickets",
    "error_logs",
    "published_country_events",
    "published_country_resources",
    "published_resource_sources_safe",
)

# Deferred pending Romain's Q2/Q4/Q5 — must NOT appear in this migration
VERIFY_TABLES: Tuple[str, ...] = (
    "case_readiness",
    "case_readiness_checklist_state",
    "case_readiness_milestone_state",
    "employee_tasks",
    "quote_requests",
)

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20260605200000_data_api_opt_out.sql"
)


@pytest.fixture(scope="module")
def migration_sql() -> str:
    assert MIGRATION_PATH.exists(), (
        f"Migration file missing: {MIGRATION_PATH}. Did FRIDAY-003b land?"
    )
    return MIGRATION_PATH.read_text()


@pytest.fixture(scope="module")
def revoke_pairs(migration_sql: str):
    """The (table, role) pairs the migration actually revokes.

    FRIDAY-003b rewrote the flat ``REVOKE … FROM …;`` statements into a
    ``to_regclass``-guarded ``do`` block that drives the REVOKEs from a
    ``(tbl, role_name, priv)`` VALUES list (replay-safe against missing tables).
    The source of truth is therefore that VALUES list, not literal REVOKE text —
    parse it. The commented-out ROLLBACK block uses ``GRANT … TO`` (a different
    shape), so it can't match this 3-tuple pattern.
    """
    pat = r"\(\s*'([a-z_]+)'\s*,\s*'(anon|authenticated)'\s*,\s*'(?:ALL|SELECT)'\s*\)"
    return {(tbl, role) for tbl, role in re.findall(pat, migration_sql)}


# ─────────────────────────────────────────────────────────────────────────────
# Static mode — always runs (CI)
# ─────────────────────────────────────────────────────────────────────────────

class TestStaticMigration:
    @pytest.mark.parametrize("table", ANON_REVOKE_TABLES)
    def test_anon_revoke_present(self, revoke_pairs, table: str) -> None:
        assert (table, "anon") in revoke_pairs, f"Missing anon REVOKE for public.{table}"

    @pytest.mark.parametrize("table", AUTHENTICATED_REVOKE_TABLES)
    def test_authenticated_revoke_present(self, revoke_pairs, table: str) -> None:
        assert (table, "authenticated") in revoke_pairs, (
            f"Missing authenticated REVOKE for public.{table}"
        )

    @pytest.mark.parametrize("table", KEEP_TABLES)
    def test_keep_tables_not_revoked(self, revoke_pairs, table: str) -> None:
        revoked = {t for t, _ in revoke_pairs}
        assert table not in revoked, (
            f"public.{table} is a KEEP table but appears in the revoke list"
        )

    @pytest.mark.parametrize("table", VERIFY_TABLES)
    def test_verify_tables_deferred(self, revoke_pairs, table: str) -> None:
        revoked = {t for t, _ in revoke_pairs}
        assert table not in revoked, (
            f"public.{table} is a VERIFY table (deferred) but appears in the revoke list"
        )

    def test_revoke_count_is_24(self, revoke_pairs) -> None:
        assert len(revoke_pairs) == 24, (
            f"Expected exactly 24 (table, role) revoke pairs, found {len(revoke_pairs)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Live mode — skipped unless RELOPASS_TEST_DB_URL is set
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def live_db_conn():
    url = os.environ.get("RELOPASS_TEST_DB_URL")
    if not url:
        pytest.skip("Set RELOPASS_TEST_DB_URL to run live-DB grant checks.")
    try:
        import psycopg2  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover
        pytest.skip("psycopg2 not installed; cannot run live-DB grant checks.")
    conn = psycopg2.connect(url)
    try:
        yield conn
    finally:
        conn.close()


def _grant_count(conn, table: str, grantee: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM information_schema.role_table_grants "
            "WHERE table_schema='public' AND table_name=%s AND grantee=%s",
            (table, grantee),
        )
        return cur.fetchone()[0]


class TestLiveGrants:
    @pytest.mark.parametrize("table", ANON_REVOKE_TABLES)
    def test_anon_grants_zero(self, live_db_conn, table: str) -> None:
        assert _grant_count(live_db_conn, table, "anon") == 0, (
            f"public.{table} still has anon grants after opt-out"
        )

    @pytest.mark.parametrize("table", AUTHENTICATED_REVOKE_TABLES)
    def test_authenticated_grants_zero(self, live_db_conn, table: str) -> None:
        assert _grant_count(live_db_conn, table, "authenticated") == 0, (
            f"public.{table} still has authenticated grants after opt-out"
        )

    @pytest.mark.parametrize("table", KEEP_TABLES)
    def test_keep_tables_retain_grants(self, live_db_conn, table: str) -> None:
        anon = _grant_count(live_db_conn, table, "anon")
        authd = _grant_count(live_db_conn, table, "authenticated")
        assert (anon + authd) > 0, (
            f"public.{table} is a KEEP table but has no anon/authenticated grants"
        )
