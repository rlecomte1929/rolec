"""SEC-RLSe (AIQ-662) — RLS triage for audit / system-only tables.

Two layers of verification:

1. Allowlist hygiene (always runs, no DB needed) — asserts the SEC-RLSe triage
   result is correctly encoded in ``supabase/rls_allowlist.txt``:
     * every server-role-only table we KEEP carries a non-empty ``# reason``;
     * the tables we PROMOTED to real policies are REMOVED from the list;
     * the parser in ``scripts/check_rls_coverage.py`` still resolves each kept
       line to the bare table name (inline comments stripped).

2. Live RLS behaviour (skipped unless Supabase creds are present) — hits the
   PostgREST REST API directly and asserts:
     * anon key cannot read any in-scope table (401/403, or RLS-empty 200 []);
     * a non-admin authenticated JWT cannot read them either;
     * an admin JWT CAN read the Path-B tables (error_logs / error_tickets);
     * the service-role key can still read every in-scope table (RLS bypass).

   To run the live layer locally / in staging CI:

       export SUPABASE_URL=https://<ref>.supabase.co
       export SUPABASE_ANON_KEY=...
       export SUPABASE_SERVICE_ROLE_KEY=...
       export RLS_TEST_NONADMIN_JWT=...   # optional, enables non-admin checks
       export RLS_TEST_ADMIN_JWT=...      # optional, enables admin-read checks
       pytest backend/tests/integration/test_rls_audit_system_tables.py -v
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWLIST_FILE = REPO_ROOT / "supabase" / "rls_allowlist.txt"

# ── SEC-RLSe scope ──────────────────────────────────────────────────────────
# Server-role-only tables KEPT on the allowlist (Path A) — must each carry a reason.
PATH_A_KEPT = [
    # Audit / event logs
    "audit_log",
    "audit_logs",
    "assignment_audit_log",
    "staging_review_audit_log",
    "policy_benefit_rule_hr_override_audit",
    "policy_assistant_answer_audits",
    "canonical_policy_query_audit_logs",
    # Crawler / ingestion background jobs
    "crawl_runs",
    "crawl_schedules",
    "crawl_job_runs",
    "crawled_source_chunks",
    "crawled_source_documents",
    "source_records",
    "research_source_candidates",
    "staged_event_candidates",
    "staged_resource_candidates",
    "knowledge_doc_ingest_jobs",
    # Policy / relocation processing jobs
    "policy_processing_runs",
    "policy_extraction_locks",
    "relocation_runs",
    "form_prefill_instances",
    "requirement_research_jobs",
    "roadmap_gap_questions",
    "roadmap_generation_jobs",
    # Freshness monitoring jobs
    "freshness_alerts",
    "freshness_snapshots",
    "document_change_events",
    # Error reporting
    "support_case_notes",
    # Notifications / outbox
    "notification_outbox",
    "ops_notification_events",
    "collaboration_notifications",
    # Sessions / admin / system
    "admin_allowlist",
    "admin_sessions",
    "sessions",
    "analytics_events",
    # Demo / prospect intake
    "demo_request_rate_limits",
    "demo_requests",
    "prospect_candidates",
    # Review queue
    "review_queue_activity_log",
    "review_queue_items",
]

# Tables PROMOTED to real RLS policies (Path B) — must be REMOVED from the allowlist.
PATH_B_REMOVED = [
    "error_logs",     # 20260502100000 + 20260530000000_rls_error_tracking_harden.sql
    "error_tickets",  # 20260502100000 + 20260530000000_rls_error_tracking_harden.sql
]

# Path-B tables an admin user is allowed to read via PostgREST.
ADMIN_READABLE = ["error_logs", "error_tickets"]


# ── Layer 1: allowlist hygiene (no DB) ──────────────────────────────────────

def _raw_lines() -> list[str]:
    return ALLOWLIST_FILE.read_text().splitlines()


def _allowlist_names() -> set[str]:
    """Replicate scripts/check_rls_coverage.py:load_allowlist parsing."""
    names: set[str] = set()
    for raw in _raw_lines():
        line = raw.split("#", 1)[0].strip()
        if line:
            names.add(line)
    return names


def _name_to_reason() -> dict[str, str]:
    """Map each table line to the text of its inline `# reason` comment."""
    out: dict[str, str] = {}
    for raw in _raw_lines():
        if not raw or raw.lstrip().startswith("#"):
            continue
        name = raw.split("#", 1)[0].strip()
        if not name:
            continue
        reason = raw.split("#", 1)[1].strip() if "#" in raw else ""
        out[name] = reason
    return out


@pytest.mark.parametrize("table", PATH_A_KEPT)
def test_path_a_table_kept_with_reason(table):
    reasons = _name_to_reason()
    assert table in reasons, f"{table} should remain on the allowlist (server-role only)"
    assert len(reasons[table]) >= 10, (
        f"{table} must carry a meaningful `# reason` comment, got: {reasons[table]!r}"
    )


@pytest.mark.parametrize("table", PATH_B_REMOVED)
def test_path_b_table_removed_from_allowlist(table):
    assert table not in _allowlist_names(), (
        f"{table} was promoted to a real RLS policy and must be removed from rls_allowlist.txt"
    )


def test_parser_resolves_kept_lines_to_bare_names():
    """The check_rls_coverage parser must still see each kept table by name."""
    names = _allowlist_names()
    for table in PATH_A_KEPT:
        assert table in names, f"parser failed to resolve {table} (inline comment handling?)"


def test_no_scope_table_listed_twice():
    raw_names = [
        raw.split("#", 1)[0].strip()
        for raw in _raw_lines()
        if raw and not raw.lstrip().startswith("#") and raw.split("#", 1)[0].strip()
    ]
    for table in PATH_A_KEPT:
        assert raw_names.count(table) == 1, f"{table} appears {raw_names.count(table)}x — expected once"


# ── Layer 2: live PostgREST RLS behaviour (skipped without creds) ────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL")
ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
NONADMIN_JWT = os.environ.get("RLS_TEST_NONADMIN_JWT")
ADMIN_JWT = os.environ.get("RLS_TEST_ADMIN_JWT")

LIVE = pytest.mark.skipif(
    not (SUPABASE_URL and ANON_KEY),
    reason="Live RLS checks need SUPABASE_URL + SUPABASE_ANON_KEY.",
)

ALL_SCOPE_TABLES = PATH_A_KEPT + PATH_B_REMOVED


def _rest_get(table: str, *, apikey: str, bearer: str | None = None):
    """GET <table>?select=*&limit=1 via PostgREST. Returns (status, body)."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?select=*&limit=1"
    req = urllib.request.Request(url, method="GET")
    req.add_header("apikey", apikey)
    req.add_header("Authorization", f"Bearer {bearer or apikey}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read() or b"[]")
    except urllib.error.HTTPError as exc:
        return exc.code, None


@LIVE
@pytest.mark.parametrize("table", ALL_SCOPE_TABLES)
def test_anon_cannot_read(table):
    status, body = _rest_get(table, apikey=ANON_KEY)
    # Acceptable: hard deny (401/403/404) OR RLS-empty (200 with []).
    if status == 200:
        assert body == [], f"anon read {len(body)} row(s) from {table} — RLS gap!"
    else:
        assert status in (401, 403, 404), f"unexpected anon status {status} for {table}"


@LIVE
@pytest.mark.skipif(not NONADMIN_JWT, reason="set RLS_TEST_NONADMIN_JWT to run")
@pytest.mark.parametrize("table", ALL_SCOPE_TABLES)
def test_nonadmin_cannot_read(table):
    status, body = _rest_get(table, apikey=ANON_KEY, bearer=NONADMIN_JWT)
    if status == 200:
        assert body == [], f"non-admin read {len(body)} row(s) from {table} — RLS gap!"
    else:
        assert status in (401, 403, 404), f"unexpected non-admin status {status} for {table}"


@LIVE
@pytest.mark.skipif(not ADMIN_JWT, reason="set RLS_TEST_ADMIN_JWT to run")
@pytest.mark.parametrize("table", ADMIN_READABLE)
def test_admin_can_read_path_b_tables(table):
    status, _ = _rest_get(table, apikey=ANON_KEY, bearer=ADMIN_JWT)
    assert status == 200, f"admin GET on {table} returned {status}, expected 200"


@LIVE
@pytest.mark.skipif(not SERVICE_KEY, reason="set SUPABASE_SERVICE_ROLE_KEY to run")
def test_service_role_can_read_all_scope_tables():
    """Service-role bypasses RLS — the backend write path must stay unbroken.

    A successful authenticated read (200) per table proves the service-role
    grant + RLS-bypass is intact; a write would mutate prod data, so we assert
    on read access which exercises the same role/grant boundary.
    """
    for table in ALL_SCOPE_TABLES:
        status, _ = _rest_get(table, apikey=SERVICE_KEY)
        assert status == 200, f"service-role GET on {table} returned {status}, expected 200"
