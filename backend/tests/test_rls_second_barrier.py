"""
F3 / AIQ-834 — regression test: the GUC-based RLS second barrier ENFORCES.

Proves that a non-BYPASSRLS role, under the request-scoped policy
`company_id = current_setting('app.current_company_id')`, returns ONLY the current
company's rows even when the query OMITS the `WHERE company_id` predicate, and
fails closed (zero rows) when the GUC is unset.

Requires a SESSION-mode Postgres connection (`SET ROLE` is unsupported by the
Supabase transaction-mode pooler on port 6543; use port 5432). Set
RELOPASS_RLS_TEST_DB_URL to run it; otherwise it SKIPS. The whole test runs in a
transaction that is ALWAYS rolled back.

It exercises the mechanism via the built-in `authenticated` role rather than
`relopass_api`, because the Supabase pooler rejects granting role membership to
its login user (so `relopass_api` can't be entered via SET ROLE over the pooler).
The barrier is a property of the RLS machinery on ANY non-BYPASSRLS role + the
GUC policy — identical to the `relopass_api` policy in production (same USING
expression; its predicate is additionally proven by the migration + a live probe).
The dependent profiles-based policy is dropped inside the rolled-back tx to
isolate the GUC policy. See scripts/verify_rls_guc_barrier.py for the standalone
runner.
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


def test_rls_second_barrier_blocks_cross_tenant() -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # Isolate to the GUC policy (drop the dependent profiles-based one).
            conn.execute(text("DROP POLICY IF EXISTS pac_select_tenant_or_admin ON public.policy_assistant_chunks"))
            conn.execute(text("GRANT SELECT ON public.policy_assistant_chunks TO authenticated"))
            conn.execute(text("DROP POLICY IF EXISTS pac_probe_guc ON public.policy_assistant_chunks"))
            conn.execute(text(
                "CREATE POLICY pac_probe_guc ON public.policy_assistant_chunks "
                "FOR SELECT TO authenticated "
                "USING (company_id = nullif(current_setting('app.current_company_id', true),'')::uuid)"
            ))
            conn.execute(text("ALTER TABLE public.policy_assistant_chunks DISABLE TRIGGER trg_audit_pac"))
            conn.execute(
                text(
                    "INSERT INTO public.policy_assistant_chunks (company_id,source_type,source_ref,chunk_text) VALUES "
                    "(:a,'matrix_benefit','b.A1','A one'),(:a,'matrix_benefit','b.A2','A two'),"
                    "(:b,'matrix_benefit','b.B1','B one'),(:b,'matrix_benefit','b.B2','B two')"
                ),
                {"a": _A, "b": _B},
            )
            conn.execute(text("ALTER TABLE public.policy_assistant_chunks ENABLE TRIGGER trg_audit_pac"))

            # Company A set, NO where clause -> only A's 2 rows.
            conn.execute(text("SET LOCAL ROLE authenticated"))
            conn.execute(text("SELECT set_config('app.current_company_id', :a, true)"), {"a": _A})
            visible = conn.execute(text("SELECT count(*) FROM public.policy_assistant_chunks")).scalar()
            conn.execute(text("RESET ROLE"))
            assert visible == 2, f"second barrier breached: saw {visible} rows, expected only company A's 2"

            # GUC unset -> fail closed (0 rows), never "all rows".
            conn.execute(text("SET LOCAL ROLE authenticated"))
            conn.execute(text("SELECT set_config('app.current_company_id', '', true)"))
            none_visible = conn.execute(text("SELECT count(*) FROM public.policy_assistant_chunks")).scalar()
            conn.execute(text("RESET ROLE"))
            assert none_visible == 0, f"unset company GUC should fail closed, saw {none_visible} rows"
        finally:
            trans.rollback()
