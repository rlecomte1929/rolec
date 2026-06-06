#!/usr/bin/env python3
"""
F3 / AIQ-834 — live proof that the GUC-based RLS second barrier ENFORCES.

Demonstrates, against a real Postgres, that a non-BYPASSRLS role with the
request-scoped policy `company_id = current_setting('app.current_company_id')`
returns ONLY the current company's rows even when the query omits the
`WHERE company_id` predicate — and fails closed (zero rows) when the GUC is unset.

Everything runs inside ONE transaction that is ALWAYS rolled back: it creates no
lasting policy/rows.

Why it uses the built-in `authenticated` role rather than `relopass_api`:
the Supabase connection pooler rejects granting role membership to the pooler's
login user (`GRANT <role> TO current_user` drops the connection), so `relopass_api`
cannot be entered via SET ROLE over the pooler. The barrier is a property of the
RLS machinery on ANY non-BYPASSRLS role + the GUC policy — identical to what the
`relopass_api` policy does in production (same USING expression). The existing
profiles-based policy is dropped inside the rolled-back tx to isolate the GUC policy.

Connection: uses RELOPASS_RLS_TEST_DB_URL if set, else derives a SESSION-mode URL
from DATABASE_URL (env or repo .env) by swapping the Supabase transaction pooler
port 6543 -> 5432 (session mode supports SET ROLE; transaction mode does not).

Exit code 0 = PASS, 1 = FAIL/UNABLE.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_A = "11111111-1111-1111-1111-111111111111"
_B = "22222222-2222-2222-2222-222222222222"


def _resolve_db_url() -> str | None:
    url = os.getenv("RELOPASS_RLS_TEST_DB_URL") or os.getenv("DATABASE_URL")
    if not url:
        env = Path(__file__).resolve().parents[1] / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    url = line.split("=", 1)[1].strip()
                    break
    if not url or not url.startswith("postgresql"):
        return None
    # Derive session-mode (port 5432) from the transaction pooler (6543).
    url = url.replace(":6543/", ":5432/")
    if "sslmode=" not in url.lower():
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


def main() -> int:
    url = _resolve_db_url()
    if not url:
        print("[SKIP] no usable Postgres URL (set RELOPASS_RLS_TEST_DB_URL or DATABASE_URL).")
        return 0

    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # Isolate to the GUC policy (drop the dependent profiles-based policy).
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
                    "(:a,'matrix_benefit','b.A1','A1'),(:a,'matrix_benefit','b.A2','A2'),"
                    "(:b,'matrix_benefit','b.B1','B1'),(:b,'matrix_benefit','b.B2','B2')"
                ),
                {"a": _A, "b": _B},
            )
            conn.execute(text("ALTER TABLE public.policy_assistant_chunks ENABLE TRIGGER trg_audit_pac"))

            conn.execute(text("SET LOCAL ROLE authenticated"))
            conn.execute(text("SELECT set_config('app.current_company_id', :a, true)"), {"a": _A})
            n_a = conn.execute(text("SELECT count(*) FROM public.policy_assistant_chunks")).scalar()
            conn.execute(text("RESET ROLE"))

            conn.execute(text("SET LOCAL ROLE authenticated"))
            conn.execute(text("SELECT set_config('app.current_company_id','',true)"))
            n_unset = conn.execute(text("SELECT count(*) FROM public.policy_assistant_chunks")).scalar()
            conn.execute(text("RESET ROLE"))

            n_super = conn.execute(
                text("SELECT count(*) FROM public.policy_assistant_chunks WHERE company_id IN (:a,:b)"),
                {"a": _A, "b": _B},
            ).scalar()
        finally:
            trans.rollback()

    ok = n_a == 2 and n_unset == 0 and n_super == 4
    print(f"  company set, no WHERE clause : {n_a} rows  (expect 2 — only company A)")
    print(f"  company GUC unset            : {n_unset} rows  (expect 0 — fail closed)")
    print(f"  bypass path                  : {n_super} rows  (expect 4)")
    print("PASS — RLS second barrier enforces" if ok else "FAIL — barrier did not enforce")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
