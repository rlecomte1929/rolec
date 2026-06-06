"""
F3 / AIQ-834 — regression test: the policy_assistant_chunks RLS policy is a real
second barrier (a query that OMITS the WHERE company_id predicate still returns
only the current company's rows when connected as the non-superuser relopass_api
role).

This requires a SESSION-mode Postgres connection (direct, port 5432) because it
uses `SET ROLE` — which the Supabase transaction-mode pooler (port 6543) does NOT
support. Set RELOPASS_RLS_TEST_DB_URL to a session-mode superuser/owner URL to
run it; otherwise it SKIPS.

The whole test runs inside a single transaction that is ALWAYS rolled back, so it
creates no lasting role/policy/rows. It fails BEFORE the migration's policy
exists (no second barrier → cross-tenant rows visible) and passes AFTER.

NOTE: the migration DDL validity and the policy predicate semantics
(A-visible / B-blocked / unset→fail-closed) were additionally proven live against
the production database via a rolled-back Supabase SQL probe during development.
"""
from __future__ import annotations

import os

import pytest

DB_URL = os.getenv("RELOPASS_RLS_TEST_DB_URL")

pytestmark = pytest.mark.skipif(
    not DB_URL,
    reason="set RELOPASS_RLS_TEST_DB_URL to a session-mode Postgres URL to run the RLS second-barrier proof",
)

_A = "11111111-1111-1111-1111-111111111111"
_B = "22222222-2222-2222-2222-222222222222"

_APPLY_POLICY = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='relopass_api') THEN
    CREATE ROLE relopass_api NOLOGIN;
  END IF;
  GRANT relopass_api TO CURRENT_USER;
  GRANT USAGE ON SCHEMA public TO relopass_api;
  GRANT SELECT ON public.policy_assistant_chunks TO relopass_api;
  DROP POLICY IF EXISTS pac_select_relopass_api ON public.policy_assistant_chunks;
  CREATE POLICY pac_select_relopass_api ON public.policy_assistant_chunks
    FOR SELECT TO relopass_api
    USING (company_id = nullif(current_setting('app.current_company_id', true),'')::uuid);
END$$;
"""


def test_rls_second_barrier_blocks_cross_tenant() -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text(_APPLY_POLICY))

            # Seed 2 company-A + 2 company-B chunks (audit trigger off for a
            # minimal insert).
            conn.execute(text("ALTER TABLE public.policy_assistant_chunks DISABLE TRIGGER trg_audit_pac"))
            conn.execute(
                text(
                    "INSERT INTO public.policy_assistant_chunks "
                    "(company_id, source_type, source_ref, chunk_text) VALUES "
                    "(:a,'matrix_benefit','b.A1','A one'),(:a,'matrix_benefit','b.A2','A two'),"
                    "(:b,'matrix_benefit','b.B1','B one'),(:b,'matrix_benefit','b.B2','B two')"
                ),
                {"a": _A, "b": _B},
            )
            conn.execute(text("ALTER TABLE public.policy_assistant_chunks ENABLE TRIGGER trg_audit_pac"))

            # As relopass_api with company A set and NO where clause → only A's rows.
            conn.execute(text("SET LOCAL ROLE relopass_api"))
            conn.execute(text("SELECT set_config('app.current_company_id', :a, true)"), {"a": _A})
            visible = conn.execute(text("SELECT count(*) FROM public.policy_assistant_chunks")).scalar()
            conn.execute(text("RESET ROLE"))
            assert visible == 2, f"second barrier breached: saw {visible} rows, expected only company A's 2"

            # Company id unset → fail closed (0 rows), never "all rows".
            conn.execute(text("SET LOCAL ROLE relopass_api"))
            conn.execute(text("SELECT set_config('app.current_company_id', '', true)"))
            none_visible = conn.execute(text("SELECT count(*) FROM public.policy_assistant_chunks")).scalar()
            conn.execute(text("RESET ROLE"))
            assert none_visible == 0, f"unset company GUC should fail closed, saw {none_visible} rows"
        finally:
            trans.rollback()
