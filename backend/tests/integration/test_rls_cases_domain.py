"""
SEC-RLSa (AIQ-658) — tenant-isolation integration tests for the cases-domain
RLS policies added in supabase/migrations/20260601000000_rls_cases_domain.sql.

These hit PostgREST DIRECTLY (not the FastAPI backend) with the public anon key
plus a per-persona Supabase JWT, so they exercise the exact path an attacker
holding the (public) anon key would use. Seeding + cleanup go through the
service-role DATABASE_URL connection, which connects as `postgres` and bypasses
RLS.

Grant reality on this project (verified, and the reason the assertions below
look the way they do):
  • `anon` has NO table privileges on any cases-domain table — it is blocked at
    the GRANT level regardless of RLS. The migration's REVOKE FROM anon is
    defense-in-depth.
  • `authenticated` has a broad CRUD grant on only a few tables. `case_readiness`
    is the important one: it was authenticated-readable with NO RLS, i.e. any
    logged-in user could read every tenant's readiness rows. The migration adds
    the assignment-scoped policy that closes that hole — and because the grant
    exists, the fix is OBSERVABLE through PostgREST, so it is what we assert the
    five-persona matrix against.
  • Every other cases-domain table is service-role-only at the GRANT level;
    authenticated/anon get 401/empty. We assert that they are NOT reachable
    (no broadened surface) rather than re-deriving per-row scoping that PostgREST
    can't even reach. The per-row scoping of those tables is covered by the
    in-migration SECURITY DEFINER helpers and the transactional SET ROLE proof
    recorded in the PR / Notion notes.

Five personas (per the execution prompt): anon, employee A (org 1), employee B
(org 2), HR admin org 1, HR admin org 2.

Requires a database with the migration APPLIED (staging / supabase branch /
local). Skips cleanly when the live-Supabase env vars are absent.

Env:
  DATABASE_URL        service-role Postgres URL (seed/cleanup, bypasses RLS)
  SUPABASE_URL        https://<ref>.supabase.co
  SUPABASE_ANON_KEY   public anon apikey (also the anon-role bearer)
  SUPABASE_JWT_SECRET legacy HS256 JWT secret (to mint per-persona JWTs)
"""
from __future__ import annotations

import os
import time
import uuid

import pytest

httpx = pytest.importorskip("httpx")
jwt = pytest.importorskip("jwt")
psycopg2 = pytest.importorskip("psycopg2")

DATABASE_URL = os.environ.get("DATABASE_URL")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (DATABASE_URL and SUPABASE_URL and ANON_KEY and JWT_SECRET),
        reason="SEC-RLSa live RLS test needs DATABASE_URL + SUPABASE_URL + "
        "SUPABASE_ANON_KEY + SUPABASE_JWT_SECRET (run against staging / a "
        "supabase branch / local with the migration applied).",
    ),
]

# Every cases-domain table the migration gives a policy to (anon must see none).
PROTECTED_TABLES = [
    "case_documents", "case_people", "case_requirement_evaluations",
    "case_readiness", "case_readiness_checklist_state", "case_readiness_milestone_state",
    "assignment_audit_log", "assignment_mobility_links", "eligibility_overrides",
    "employee_answers", "case_participants", "case_requirements_snapshots",
    "relocation_artifacts", "relocation_runs", "relocation_sources",
    "case_evidence", "case_feedback", "assignment_policy_service_comparisons",
    "resolved_assignment_policies", "resolved_assignment_policy_benefits",
    "resolved_assignment_policy_exclusions", "profile_state", "answers",
    "case_assignment_id", "wizard_cases",
]
TEMPLATE_TABLES = [
    "readiness_templates",
    "readiness_template_checklist_items",
    "readiness_template_milestones",
]
# Backend-only tables: authenticated has no grant, so a user JWT must get nothing.
BACKEND_ONLY_SAMPLE = [
    "employee_answers", "case_documents", "resolved_assignment_policies",
    "case_evidence", "answers", "profile_state",
]


def _uuid() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="module")
def seed():
    """Seed two single-tenant orgs into case_readiness and return identifiers."""
    tag = f"rlstest_{uuid.uuid4().hex[:12]}"
    ctx = {
        "tag": tag,
        "emp_a": _uuid(), "emp_b": _uuid(), "hr_1": _uuid(), "hr_2": _uuid(),
        "company_1": f"{tag}_co1", "company_2": f"{tag}_co2",
        "asgn_a": f"{tag}_asgnA", "asgn_b": f"{tag}_asgnB",
        "case_a": f"{tag}_caseA", "case_b": f"{tag}_caseB",
        "template": f"{tag}_tmpl",
        "sentinel": tag,  # case_readiness.destination_key marker
    }
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO readiness_templates (id, destination_key, route_title) "
                "VALUES (%s,%s,%s)",
                (ctx["template"], ctx["sentinel"], "RLS test"),
            )
            cur.execute(
                "INSERT INTO hr_users (id, company_id, profile_id, created_at) "
                "VALUES (%s,%s,%s,'t'),(%s,%s,%s,'t')",
                (ctx["hr_1"], ctx["company_1"], tag, ctx["hr_2"], ctx["company_2"], tag),
            )
            cur.execute(
                "INSERT INTO case_assignments "
                "(id, case_id, employee_user_id, hr_user_id, employee_identifier) "
                "VALUES (%s,%s,%s,%s,%s),(%s,%s,%s,%s,%s)",
                (ctx["asgn_a"], ctx["case_a"], ctx["emp_a"], ctx["hr_1"], tag,
                 ctx["asgn_b"], ctx["case_b"], ctx["emp_b"], ctx["hr_2"], tag),
            )
            cur.execute(
                "INSERT INTO case_readiness "
                "(assignment_id, template_id, destination_key, route_key) "
                "VALUES (%s,%s,%s,'r'),(%s,%s,%s,'r')",
                (ctx["asgn_a"], ctx["template"], ctx["sentinel"],
                 ctx["asgn_b"], ctx["template"], ctx["sentinel"]),
            )
        yield ctx
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM case_readiness WHERE destination_key=%s", (ctx["sentinel"],))
            cur.execute("DELETE FROM case_assignments WHERE employee_identifier=%s", (tag,))
            cur.execute("DELETE FROM hr_users WHERE profile_id=%s", (tag,))
            cur.execute("DELETE FROM readiness_templates WHERE id=%s", (ctx["template"],))
        conn.close()


def _mint(sub: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "role": "authenticated", "aud": "authenticated",
         "iat": now, "exp": now + 3600},
        JWT_SECRET, algorithm="HS256",
    )


def _rest_get(table: str, params: dict, bearer: str):
    headers = {"apikey": ANON_KEY, "Authorization": f"Bearer {bearer}"}
    with httpx.Client(timeout=20) as client:
        r = client.get(f"{SUPABASE_URL}/rest/v1/{table}", params=params, headers=headers)
    rows = r.json() if r.status_code == 200 else None
    return r.status_code, rows


def _readiness_rows(assignment_id: str, sentinel: str, bearer: str) -> int:
    status, rows = _rest_get(
        "case_readiness",
        {"destination_key": f"eq.{sentinel}", "assignment_id": f"eq.{assignment_id}", "select": "*"},
        bearer,
    )
    if status == 200 and isinstance(rows, list):
        return len(rows)
    assert status in (401, 403, 404), f"case_readiness: unexpected status {status}"
    return 0


def test_anon_cannot_read_any_protected_table(seed):
    """Persona 1 — the public anon key surfaces zero rows on every table."""
    leaks = []
    for table in PROTECTED_TABLES:
        status, rows = _rest_get(table, {"select": "*", "limit": "1"}, ANON_KEY)
        if status == 200 and isinstance(rows, list) and rows:
            leaks.append(table)
    assert not leaks, f"anon key leaked rows from: {leaks}"


def test_migration_applied_precondition(seed):
    """Guard: an authenticated stranger reading case_readiness must see 0 of our
    seeded rows. If they see them, RLS is not applied to this database."""
    stranger = _mint(_uuid())
    status, rows = _rest_get(
        "case_readiness", {"destination_key": f"eq.{seed['sentinel']}", "select": "*"}, stranger
    )
    seen = len(rows) if status == 200 and isinstance(rows, list) else 0
    assert seen == 0, (
        "an authenticated stranger could read seeded case_readiness rows — "
        "20260601000000_rls_cases_domain.sql is not applied to this database."
    )


def test_employee_tenant_isolation(seed):
    """Personas 2 & 3 — each employee sees only their own org's readiness row."""
    emp_a, emp_b = _mint(seed["emp_a"]), _mint(seed["emp_b"])
    assert _readiness_rows(seed["asgn_a"], seed["sentinel"], emp_a) == 1, "employee A cannot see own row"
    assert _readiness_rows(seed["asgn_b"], seed["sentinel"], emp_a) == 0, "employee A leaked org-2 row"
    assert _readiness_rows(seed["asgn_b"], seed["sentinel"], emp_b) == 1, "employee B cannot see own row"
    assert _readiness_rows(seed["asgn_a"], seed["sentinel"], emp_b) == 0, "employee B leaked org-1 row"


def test_hr_company_tenant_isolation(seed):
    """Personas 4 & 5 — HR sees their own company's row, never the other org's."""
    hr_1, hr_2 = _mint(seed["hr_1"]), _mint(seed["hr_2"])
    assert _readiness_rows(seed["asgn_a"], seed["sentinel"], hr_1) == 1, "HR org-1 cannot see org-1 row"
    assert _readiness_rows(seed["asgn_b"], seed["sentinel"], hr_1) == 0, "HR org-1 leaked org-2 row"
    assert _readiness_rows(seed["asgn_b"], seed["sentinel"], hr_2) == 1, "HR org-2 cannot see org-2 row"
    assert _readiness_rows(seed["asgn_a"], seed["sentinel"], hr_2) == 0, "HR org-2 leaked org-1 row"


def test_backend_only_tables_not_reachable_by_authenticated(seed):
    """No broadened surface — a normal user JWT gets nothing from service-role-only
    tables (blocked at the GRANT level; RLS is the second line of defense)."""
    user = _mint(seed["emp_a"])
    for table in BACKEND_ONLY_SAMPLE:
        status, rows = _rest_get(table, {"select": "*", "limit": "1"}, user)
        reachable = status == 200 and isinstance(rows, list) and len(rows) > 0
        assert not reachable, f"{table}: authenticated unexpectedly read rows (status {status})"


def test_templates_readable_by_any_authenticated(seed):
    """Template tables are public-read for authenticated users, denied to anon."""
    user = _mint(seed["emp_a"])
    for table in TEMPLATE_TABLES:
        status, _ = _rest_get(table, {"select": "*", "limit": "1"}, user)
        assert status == 200, f"{table}: authenticated read should be allowed (got {status})"
        a_status, a_rows = _rest_get(table, {"select": "*", "limit": "1"}, ANON_KEY)
        assert not (a_status == 200 and a_rows), f"{table}: anon read leaked rows"
