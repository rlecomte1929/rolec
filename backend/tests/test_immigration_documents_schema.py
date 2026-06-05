"""BL-OCR.1 / AIQ-747 — static schema guard for the immigration_documents migration.

Mirrors the static-mode pattern of test_data_api_opt_out.py: parses the migration
SQL (comment lines stripped, so only executing statements are asserted) and locks
in the CLAUDE.md hard gate for any new public table — RLS enabled + at least one
policy + anon revoked — plus the SEC-006 bucket hardening for the private
'immigration-documents' storage bucket.

No DB credentials required; this is what CI exercises. The upload/read round-trip
and cross-tenant isolation behaviour was verified live against the baseline schema
during AIQ-747 (see the task's Execution Notes).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20260609120000_immigration_documents.sql"
)


@pytest.fixture(scope="module")
def active_sql() -> str:
    assert MIGRATION_PATH.exists(), f"Migration file missing: {MIGRATION_PATH}"
    raw = MIGRATION_PATH.read_text()
    lines = [ln for ln in raw.splitlines() if not ln.lstrip().startswith("--")]
    return "\n".join(lines)


def test_table_created(active_sql: str) -> None:
    assert re.search(
        r"create table if not exists\s+public\.immigration_documents",
        active_sql, re.IGNORECASE,
    ), "immigration_documents table not created idempotently"


def test_rls_hard_gate(active_sql: str) -> None:
    # 1. RLS enabled
    assert re.search(
        r"alter table\s+public\.immigration_documents\s+enable row level security",
        active_sql, re.IGNORECASE,
    ), "RLS not enabled on immigration_documents"
    # 2. anon revoked (defence-in-depth)
    assert re.search(
        r"revoke all on\s+public\.immigration_documents\s+from anon",
        active_sql, re.IGNORECASE,
    ), "anon access not revoked on immigration_documents"
    # 3. at least the read + write + service_role policies
    for policy in (
        "immigration_documents_select",
        "immigration_documents_insert",
        "immigration_documents_service_role",
    ):
        assert f"create policy {policy}" in active_sql.lower(), f"missing policy: {policy}"


def test_tenant_scoping_via_case_assignments(active_sql: str) -> None:
    # Isolation is enforced by a case_assignments join, not an org_id JWT claim.
    assert "auth.jwt()" not in active_sql.lower(), "must not use org_id JWT claim in this codebase"
    assert "public.case_assignments" in active_sql.lower()
    assert "auth.uid()::text" in active_sql.lower()


def test_no_hard_fk_to_baseline_only_table(active_sql: str) -> None:
    # immigration_cases lives only in the remote baseline; a hard FK would break
    # fresh replay. The link must be a soft TEXT column.
    assert not re.search(
        r"references\s+public\.immigration_cases", active_sql, re.IGNORECASE
    ), "hard FK to immigration_cases breaks fresh replay — use a soft TEXT link"


def test_bucket_private_and_hardened(active_sql: str) -> None:
    lower = active_sql.lower()
    assert "insert into storage.buckets" in lower
    assert "'immigration-documents'" in lower
    # private (public = false) + SEC-006 size cap
    assert re.search(r"'immigration-documents'.*?false", lower, re.DOTALL), "bucket must be private"
    assert "20971520" in active_sql, "bucket must carry the 20 MiB SEC-006 size cap"
    # idempotent insert
    assert "on conflict (id) do nothing" in lower
    # storage object policies for read + write
    for policy in ("immigration_documents_objects_read", "immigration_documents_objects_write"):
        assert f"create policy {policy}" in lower, f"missing storage policy: {policy}"
