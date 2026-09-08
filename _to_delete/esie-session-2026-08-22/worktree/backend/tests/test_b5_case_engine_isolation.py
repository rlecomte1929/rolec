"""SEC-RLSc (AIQ-660) — guard that the rce tenant-RLS migration replaces the
permissive C1-01 policies and scopes every tenant table. Extends the B5 pattern
to the rce.* Case Engine schema.

Static mode (CI): parses the migration SQL.
Live mode (RELOPASS_TEST_DB_URL): asserts no permissive authenticated policy
survives on tenant tables.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"

CASE_SCOPED = (
    "family_members", "documents", "deadlines", "costs", "corrections", "agent_runs",
)
EMPLOYER_SCOPED = ("employers", "employees", "hr_policies", "policy_clauses")
TRANSITIVE = ("extracted_fields", "entity_links")


@pytest.fixture(scope="module")
def migration_sql() -> str:
    matches = sorted(MIGRATIONS_DIR.glob("*_rce_tenant_rls.sql"))
    assert matches, "SEC-RLSc migration *_rce_tenant_rls.sql not found"
    return matches[-1].read_text()


class TestRceTenantRlsStatic:
    def test_drops_all_existing_rce_policies(self, migration_sql: str) -> None:
        assert re.search(
            r"pg_policies\s+where\s+schemaname\s*=\s*'rce'", migration_sql, re.IGNORECASE
        ), "migration must dynamically drop existing rce policies"
        assert re.search(r"drop\s+policy\s+if\s+exists", migration_sql, re.IGNORECASE)

    def test_safe_default_service_only_loop(self, migration_sql: str) -> None:
        assert re.search(r"enable\s+row\s+level\s+security", migration_sql, re.IGNORECASE)
        assert re.search(r"revoke\s+all\s+on\s+rce\.", migration_sql, re.IGNORECASE)
        assert re.search(r"to\s+service_role", migration_sql, re.IGNORECASE)

    def test_safe_default_revokes_authenticated(self, migration_sql: str) -> None:
        # C1-01 left permissive DML grants on some rce tables (extraction_agents,
        # agent_versions). The §4a safe-default loop must revoke authenticated too,
        # not just anon, or those tables keep stale INSERT/UPDATE/DELETE grants.
        assert re.search(
            r"revoke\s+all\s+on\s+rce\.[^;]*from\s+anon\s*,\s*authenticated",
            migration_sql, re.IGNORECASE,
        ), "safe-default loop must revoke ALL from both anon AND authenticated"

    def test_no_permissive_authenticated_true_on_tenant_tables(self, migration_sql: str) -> None:
        # No blanket `for all to authenticated ... using (true)` may remain.
        assert not re.search(
            r"for\s+all\s+to\s+authenticated[^;]*using\s*\(\s*true\s*\)",
            migration_sql, re.IGNORECASE | re.DOTALL,
        ), "no permissive FOR ALL authenticated USING(true) may remain"

    def test_addresses_not_authenticated_readable(self, migration_sql: str) -> None:
        # rce.addresses holds applicant address PII -> must stay service-only,
        # i.e. no authenticated reference-read policy for it.
        assert "addresses_ref_read" not in migration_sql, (
            "rce.addresses is PII and must not get an authenticated read policy"
        )

    def test_helpers_defined(self, migration_sql: str) -> None:
        for fn in ("rce.current_hr_company", "rce.can_access_case", "rce.can_access_employer"):
            assert re.search(rf"function\s+{re.escape(fn)}\b", migration_sql, re.IGNORECASE), fn

    def test_grants_select_to_authenticated(self, migration_sql: str) -> None:
        # RLS policies are inert without a table grant: prior C1-01a revoked
        # authenticated grants on rce.*, so every tenant/ref read policy must be
        # paired with a `grant select ... to authenticated` or it filters to a
        # permission-denied, not RLS-scoped rows.
        assert re.search(
            r"grant\s+select\s+on\s+rce\.[^;]*to\s+authenticated",
            migration_sql, re.IGNORECASE,
        ), "tenant/ref read policies must grant select to authenticated"

    def test_service_only_tables_get_no_authenticated_grant(self, migration_sql: str) -> None:
        # The deliberately service-only tables must never be granted to authenticated.
        for t in ("addresses", "canonical_entities", "extraction_agents", "agent_versions"):
            assert not re.search(
                rf"grant\s+select\s+on\s+rce\.{t}\b[^;]*to\s+authenticated",
                migration_sql, re.IGNORECASE,
            ), f"rce.{t} must stay service-only (no authenticated grant)"

    @pytest.mark.parametrize("table", CASE_SCOPED)
    def test_case_scoped_select_policy(self, migration_sql: str, table: str) -> None:
        assert re.search(rf"\b{table}\b", migration_sql), table
        assert "rce.can_access_case" in migration_sql

    @pytest.mark.parametrize("table", EMPLOYER_SCOPED + TRANSITIVE)
    def test_named_tenant_select_policy(self, migration_sql: str, table: str) -> None:
        assert re.search(rf"{table}_tenant_select", migration_sql), f"{table}_tenant_select missing"

    def test_self_contained_no_sibling_dependency(self, migration_sql: str) -> None:
        assert "public.rls_current_hr_company" not in migration_sql, (
            "must not depend on the SEC-RLSa sibling helper (ordering risk)"
        )


# ----- live mode -----
def _live_conn():
    url = os.environ.get("RELOPASS_TEST_DB_URL")
    if not url:
        pytest.skip("Set RELOPASS_TEST_DB_URL (migration applied) to run live RLS checks.")
    try:
        import psycopg2
    except ImportError:  # pragma: no cover
        pytest.skip("psycopg2 not installed")
    return psycopg2.connect(url)


@pytest.mark.integration
class TestRceTenantRlsLive:
    def test_no_permissive_policy_remains(self) -> None:
        conn = _live_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select tablename, policyname, qual
                    from pg_policies
                    where schemaname='rce'
                      and 'authenticated' = any(roles)
                      and coalesce(qual,'') in ('true','(true)')
                      and tablename in ('cases','documents','extracted_fields',
                                        'family_members','deadlines','costs',
                                        'corrections','employers','employees',
                                        'hr_policies','policy_clauses','entity_links',
                                        'contradictions','rule_citations')
                    """
                )
                leaks = cur.fetchall()
            assert not leaks, f"permissive authenticated policies remain: {leaks}"
        finally:
            conn.close()
