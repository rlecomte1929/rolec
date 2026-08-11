-- RLS for the two ROR (relocation-ranking) ops tables.
--
-- `ror_cities` and `ror_queue` were created in public on 2026-08-11 with no RLS, no
-- policy and no REVOKE — see 20260811170803_ror_coverage_ledger.sql, the reconciliation
-- of that out-of-band apply. CLAUDE.md § "Database Migrations — Security Rules" makes all
-- three mandatory for any new `public` table, because Supabase exposes public via
-- PostgREST and the anon key ships in the frontend bundle. That omission is what SEC-002
-- was (8 tables, GDPR-scope PII exposure).
--
-- Neither table is exposed TODAY: verified 2026-08-11 that both have rls_enabled = false,
-- 0 policies, and NO grant to `anon` or `authenticated` — the two roles PostgREST uses —
-- so nothing was readable with the anon key. Contents are non-personal as well:
-- ror_cities (700 rows) is a city-ranking catalogue, ror_queue (8,470 rows) a rollout work
-- queue. This closes the gap before a routine GRANT makes it matter, rather than after.
--
-- Follows 20260605300000_rls_defense_in_depth_service_role.sql exactly: RLS on, one
-- explicit service_role ALL policy, REVOKE anon. service_role BYPASSES RLS, so the
-- backend's access is unchanged — no read path is being taken away.
--
-- Deliberately NO `authenticated` policy: there is no supabase-js `.from('ror_*')` path in
-- the frontend, so a tenant-scoped policy would be dead code. Add one, with a GRANT, if a
-- direct client read path is ever needed.
--
-- Once this is applied to prod, DELETE the two ror_* lines from
-- supabase/rls_allowlist.txt — check_rls_coverage.py will report them as stale.
--
-- Replay-safe: DROP POLICY IF EXISTS before CREATE; REVOKE is a no-op when the grant was
-- never present; missing tables are skipped so a fresh `supabase db reset` works.

DO $$
DECLARE
  t text;
  tables text[] := ARRAY['ror_cities', 'ror_queue'];
BEGIN
  FOREACH t IN ARRAY tables LOOP
    IF to_regclass('public.' || t) IS NULL THEN
      RAISE NOTICE 'skipping missing table public.%', t;
      CONTINUE;
    END IF;

    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', t);

    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I;', t || '_service_role_all', t);
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true);',
      t || '_service_role_all', t
    );

    EXECUTE format('REVOKE ALL ON public.%I FROM anon;', t);
  END LOOP;
END$$;
