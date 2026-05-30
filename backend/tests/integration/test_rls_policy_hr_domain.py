"""
SEC-RLSb (AIQ-659) — RLS integration tests for the policy / HR domain added in
supabase/migrations/20260531010000_rls_policy_hr_domain.sql.

Two complementary layers, because of how THIS project is wired:

  * In ReloPass the `anon` AND `authenticated` PostgREST roles have **no table
    grants** on application tables — the frontend reads policy/HR data through
    the FastAPI backend (service-role / direct Postgres), never PostgREST. RLS
    here is therefore defense-in-depth: the anon hole is closed by RLS-enable +
    `revoke ... from anon` + the absence of any authenticated grant.

  * Layer 1 (httpx → PostgREST, mirrors SEC-RLSa): proves the real attacker path
    — the public anon key — surfaces zero rows on every protected table.

  * Layer 2 (psycopg2, self-contained): proves the *scoping logic* (HR sees only
    its own company; non-HR/anon see nothing; shared knowledge is readable;
    server-internal tables are hidden from authenticated). It seeds two
    single-tenant orgs, then for each persona runs the RLS qual under
    `SET LOCAL ROLE authenticated` + a synthetic `request.jwt.claims`, granting
    SELECT *inside a rolled-back transaction* so the grant never persists. This
    validates the policies regardless of the ambient grant model and without
    mutating the database.

Personas (per the execution prompt):
  1. Anon                         → no rows on any table.
  2. HR admin org 1               → only org-1 policy artifacts; never org 2's.
  3. HR admin org 2               → only org-2 policy artifacts; never org 1's.
  4. Authenticated non-HR (≈ employee) → nothing on company-scoped tables.
  5. Service role                 → full access (backend extract pipelines).

Env:
  DATABASE_URL       service-role Postgres URL (seed/cleanup + Layer 2; bypasses RLS)
  SUPABASE_URL       https://<ref>.supabase.co        (Layer 1 only)
  SUPABASE_ANON_KEY  public anon apikey               (Layer 1 only)
"""
from __future__ import annotations

import json
import os
import uuid

import pytest

psycopg2 = pytest.importorskip("psycopg2")

DATABASE_URL = os.environ.get("DATABASE_URL")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

# Every policy/HR-domain table this migration gives a policy to (drained from
# supabase/rls_allowlist.txt by SEC-RLSb). 35 tables.
PROTECTED_TABLES = [
    # direct company_id
    "company_policies", "company_preferred_suppliers", "company_policy_assistant_bindings",
    "policy_assistant_answer_audits", "policy_configs", "policy_documents",
    "policy_knowledge_snapshots", "company_vendor_selections",
    # children of policy_documents
    "policy_document_chunks", "policy_document_clauses", "policy_processing_runs",
    # policy_knowledge_snapshots child
    "policy_facts",
    # policy_versions + its children
    "policy_versions", "policy_assignment_type_applicability", "policy_benefit_rules",
    "policy_benefit_rule_hr_overrides", "policy_evidence_requirements", "policy_exclusions",
    "policy_family_status_applicability", "policy_rule_conditions", "policy_source_links",
    "policy_tier_overrides",
    # policy_configs chain
    "policy_config_versions", "policy_config_benefits", "policy_benefit_jurisdiction_overrides",
    "policy_benefit_rule_hr_override_audit",
    # assignment-scoped HR
    "compliance_actions", "compliance_reports",
    # shared knowledge graph (authenticated read / admin write)
    "canonical_policy_documents", "canonical_policy_document_chunks", "canonical_policy_facts",
    "canonical_policy_fact_validation_errors", "policy_rules",
    # server-internal (service_role only)
    "policy_extraction_locks", "hr_policies",
]

SHARED_TABLES = [
    "canonical_policy_documents", "canonical_policy_document_chunks",
    "canonical_policy_facts", "canonical_policy_fact_validation_errors", "policy_rules",
]
SERVER_INTERNAL_TABLES = ["policy_extraction_locks", "hr_policies"]


# ───────────────────────────────────────── seed fixture (committed) ─────────
@pytest.fixture(scope="module")
def seed():
    if not DATABASE_URL:
        pytest.skip("SEC-RLSb RLS test needs DATABASE_URL (migration applied).")
    tag = f"rlsb_{uuid.uuid4().hex[:12]}"
    ctx = {
        "tag": tag,
        "hr_1": str(uuid.uuid4()),          # auth uid (HR, org 1) == hr_users.profile_id
        "hr_2": str(uuid.uuid4()),          # auth uid (HR, org 2)
        "non_hr": str(uuid.uuid4()),        # authenticated user with no hr_users row
        "company_1": str(uuid.uuid4()),     # company_id (uuid rendered as text)
        "company_2": str(uuid.uuid4()),
        "doc_a": str(uuid.uuid4()), "doc_b": str(uuid.uuid4()),
        "cp_a": str(uuid.uuid4()), "cp_b": str(uuid.uuid4()),
        "canon_id": f"{tag}_canon",
        "hp_id": f"{tag}_hp",
        "sentinel": f"{tag}_S",
    }
    s, now = ctx["sentinel"], "2026-05-30T00:00:00Z"
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            # hr_users: profile_id == auth uid (that is what hr_company_ids() matches on)
            cur.execute(
                "INSERT INTO hr_users (id, company_id, profile_id, created_at) "
                "VALUES (%s,%s,%s,%s),(%s,%s,%s,%s)",
                (ctx["hr_1"], ctx["company_1"], ctx["hr_1"], now,
                 ctx["hr_2"], ctx["company_2"], ctx["hr_2"], now),
            )
            # policy_documents — direct company_id
            cur.execute(
                "INSERT INTO policy_documents "
                "(id, company_id, uploaded_by_user_id, filename, mime_type, storage_path) "
                "VALUES (%s,%s,%s,%s,%s,%s),(%s,%s,%s,%s,%s,%s)",
                (ctx["doc_a"], ctx["company_1"], ctx["hr_1"], s, "application/pdf", s,
                 ctx["doc_b"], ctx["company_2"], ctx["hr_2"], s, "application/pdf", s),
            )
            # company_policies — direct company_id
            cur.execute(
                "INSERT INTO company_policies (id, company_id, title, file_url, file_type) "
                "VALUES (%s,%s,%s,%s,%s),(%s,%s,%s,%s,%s)",
                (ctx["cp_a"], ctx["company_1"], s, s, "pdf",
                 ctx["cp_b"], ctx["company_2"], s, s, "pdf"),
            )
            # policy_versions — scoped via company_policies(policy_id)
            cur.execute(
                "INSERT INTO policy_versions (policy_id, created_by) VALUES (%s,%s),(%s,%s)",
                (ctx["cp_a"], tag, ctx["cp_b"], tag),
            )
            # policy_document_chunks — scoped via policy_documents(policy_document_id)
            cur.execute(
                "INSERT INTO policy_document_chunks (policy_document_id, chunk_index, text_content) "
                "VALUES (%s,%s,%s),(%s,%s,%s)",
                (ctx["doc_a"], 0, s, ctx["doc_b"], 0, s),
            )
            # canonical_policy_documents — shared knowledge graph (one row is enough)
            cur.execute(
                "INSERT INTO canonical_policy_documents "
                "(id, company_id, source_type, assignment_types_json, metadata_json, "
                " ingestion_status, extraction_status) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (ctx["canon_id"], ctx["company_1"], "test", "[]", "{}", "done", "done"),
            )
            # hr_policies — server-internal (locked to service_role)
            cur.execute(
                "INSERT INTO hr_policies (id, policy_json, status, company_entity, created_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (ctx["hp_id"], "{}", "active", tag, now, now),
            )
        yield ctx
    finally:
        with conn.cursor() as cur:
            # children before parents (FKs)
            cur.execute("DELETE FROM policy_document_chunks WHERE text_content=%s", (s,))
            cur.execute("DELETE FROM policy_versions WHERE created_by=%s", (tag,))
            cur.execute("DELETE FROM company_policies WHERE title=%s", (s,))
            cur.execute("DELETE FROM policy_documents WHERE filename=%s", (s,))
            cur.execute("DELETE FROM canonical_policy_documents WHERE id=%s", (ctx["canon_id"],))
            cur.execute("DELETE FROM hr_policies WHERE company_entity=%s", (tag,))
            cur.execute("DELETE FROM hr_users WHERE id IN (%s,%s)", (ctx["hr_1"], ctx["hr_2"]))
        conn.close()


# ───────────────────────────────────── Layer 2: in-DB RLS simulation ────────
def _count_as(conn, *, table, where, grants, sub=None, role="authenticated"):
    """
    Count rows visible to `role` (with optional JWT `sub`) — running the table's
    RLS quals for real. SELECT is granted to `authenticated` only for the life of
    a transaction that is always rolled back, so nothing persists. A permission
    error (no grant / denied) counts as zero visibility.
    """
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            if grants:
                cur.execute("GRANT SELECT ON %s TO authenticated"
                            % ", ".join("public." + g for g in grants))
            cur.execute("SET LOCAL ROLE %s" % role)
            claims = json.dumps({"sub": sub, "role": role}) if sub else json.dumps({"role": role})
            cur.execute("SELECT set_config('request.jwt.claims', %s, true)", (claims,))
            try:
                cur.execute("SELECT count(*) FROM public.%s WHERE %s" % (table, where))
                return cur.fetchone()[0]
            except psycopg2.Error:
                return 0
    finally:
        conn.rollback()  # drops the grant, the role and the claims


@pytest.fixture()
def conn():
    c = psycopg2.connect(DATABASE_URL)
    try:
        yield c
    finally:
        c.close()


@pytest.mark.integration
def test_all_tables_have_rls_and_a_policy(seed, conn):
    """Precondition: every protected table has RLS enabled + ≥1 policy + no anon priv."""
    conn.autocommit = True
    missing_rls, missing_policy, anon_priv = [], [], []
    with conn.cursor() as cur:
        for t in PROTECTED_TABLES:
            cur.execute("SELECT relrowsecurity FROM pg_class "
                        "WHERE relname=%s AND relnamespace='public'::regnamespace", (t,))
            row = cur.fetchone()
            if not row or not row[0]:
                missing_rls.append(t)
            cur.execute("SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename=%s", (t,))
            if cur.fetchone()[0] == 0:
                missing_policy.append(t)
            cur.execute("SELECT has_table_privilege('anon','public.'||%s,'SELECT')", (t,))
            if cur.fetchone()[0]:
                anon_priv.append(t)
    assert not missing_rls, f"RLS not enabled on: {missing_rls}"
    assert not missing_policy, f"no policy on: {missing_policy}"
    assert not anon_priv, f"anon still has SELECT on: {anon_priv}"


@pytest.mark.integration
def test_hr_company_isolation_direct(seed, conn):
    """HR sees only its own company's directly-scoped rows (policy_documents, company_policies)."""
    s = seed["sentinel"]
    cases = [
        ("policy_documents", "filename", ["policy_documents"]),
        ("company_policies", "title", ["company_policies"]),
    ]
    for table, col, grants in cases:
        a = f"{col}='{s}' AND company_id='{seed['company_1']}'"
        b = f"{col}='{s}' AND company_id='{seed['company_2']}'"
        assert _count_as(conn, table=table, where=a, grants=grants, sub=seed["hr_1"]) == 1, \
            f"{table}: HR org-1 cannot see own row"
        assert _count_as(conn, table=table, where=b, grants=grants, sub=seed["hr_1"]) == 0, \
            f"{table}: HR org-1 LEAKED org-2 row"
        assert _count_as(conn, table=table, where=b, grants=grants, sub=seed["hr_2"]) == 1, \
            f"{table}: HR org-2 cannot see own row"
        assert _count_as(conn, table=table, where=a, grants=grants, sub=seed["hr_2"]) == 0, \
            f"{table}: HR org-2 LEAKED org-1 row"


@pytest.mark.integration
def test_hr_company_isolation_via_joins(seed, conn):
    """Join-scoped children isolate too (policy_versions→company_policies,
    policy_document_chunks→policy_documents)."""
    s, tag = seed["sentinel"], seed["tag"]
    # policy_versions: scoped through company_policies(policy_id) via SECURITY DEFINER fn
    pv_a = f"created_by='{tag}' AND policy_id='{seed['cp_a']}'"
    pv_b = f"created_by='{tag}' AND policy_id='{seed['cp_b']}'"
    assert _count_as(conn, table="policy_versions", where=pv_a, grants=["policy_versions"], sub=seed["hr_1"]) == 1
    assert _count_as(conn, table="policy_versions", where=pv_b, grants=["policy_versions"], sub=seed["hr_1"]) == 0
    assert _count_as(conn, table="policy_versions", where=pv_b, grants=["policy_versions"], sub=seed["hr_2"]) == 1
    # policy_document_chunks: inline EXISTS on policy_documents (needs both granted)
    g = ["policy_document_chunks", "policy_documents"]
    ch_a = f"text_content='{s}' AND policy_document_id='{seed['doc_a']}'"
    ch_b = f"text_content='{s}' AND policy_document_id='{seed['doc_b']}'"
    assert _count_as(conn, table="policy_document_chunks", where=ch_a, grants=g, sub=seed["hr_1"]) == 1
    assert _count_as(conn, table="policy_document_chunks", where=ch_b, grants=g, sub=seed["hr_1"]) == 0
    assert _count_as(conn, table="policy_document_chunks", where=ch_b, grants=g, sub=seed["hr_2"]) == 1


@pytest.mark.integration
def test_non_hr_authenticated_sees_nothing(seed, conn):
    """Persona 4 — an authenticated user with no hr_users row sees no company data."""
    s = seed["sentinel"]
    for table, col, grants in [("policy_documents", "filename", ["policy_documents"]),
                               ("company_policies", "title", ["company_policies"])]:
        for company in (seed["company_1"], seed["company_2"]):
            where = f"{col}='{s}' AND company_id='{company}'"
            assert _count_as(conn, table=table, where=where, grants=grants, sub=seed["non_hr"]) == 0, \
                f"{table}: non-HR user saw a row"


@pytest.mark.integration
def test_server_internal_hidden_from_authenticated(seed, conn):
    """hr_policies / policy_extraction_locks have NO authenticated policy → 0 even for HR."""
    where = f"company_entity='{seed['tag']}'"
    assert _count_as(conn, table="hr_policies", where=where, grants=["hr_policies"], sub=seed["hr_1"]) == 0, \
        "hr_policies leaked to an authenticated HR user"


@pytest.mark.integration
def test_shared_knowledge_readable_by_any_authenticated(seed, conn):
    """canonical_policy_documents is shared — any authenticated user (even non-HR) reads it,
    but anon cannot."""
    where = f"id='{seed['canon_id']}'"
    g = ["canonical_policy_documents"]
    assert _count_as(conn, table="canonical_policy_documents", where=where, grants=g, sub=seed["non_hr"]) == 1, \
        "shared canonical doc not readable by authenticated user"
    # anon role: revoked + no grant → denied → 0
    assert _count_as(conn, table="canonical_policy_documents", where=where, grants=[], role="anon") == 0, \
        "shared canonical doc leaked to anon role"


@pytest.mark.integration
def test_service_role_bypass_intact(seed, conn):
    """Persona 5 — the backend (service role / login role) still sees seeded rows."""
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM public.policy_documents WHERE filename=%s", (seed["sentinel"],))
        assert cur.fetchone()[0] == 2, "service-role/login path cannot read its own data"


# ───────────────────────────────── Layer 1: anon via PostgREST (httpx) ──────
@pytest.mark.integration
def test_anon_postgrest_reads_nothing(seed):
    """The public anon key must surface zero rows on every protected table."""
    if not (SUPABASE_URL and ANON_KEY):
        pytest.skip("Layer-1 anon PostgREST check needs SUPABASE_URL + SUPABASE_ANON_KEY.")
    httpx = pytest.importorskip("httpx")
    headers = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}
    leaks = []
    with httpx.Client(timeout=20) as client:
        for table in PROTECTED_TABLES:
            r = client.get(f"{SUPABASE_URL}/rest/v1/{table}",
                           params={"select": "*", "limit": "1"}, headers=headers)
            if r.status_code == 200:
                try:
                    rows = r.json()
                except Exception:
                    rows = None
                if isinstance(rows, list) and rows:
                    leaks.append(table)
            else:
                assert r.status_code in (401, 403, 404), f"{table}: unexpected status {r.status_code}"
    assert not leaks, f"anon key leaked rows from: {leaks}"
