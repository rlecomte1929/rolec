-- Pin `search_path = ''` on the SQL/PLPGSQL functions in `public` that the
-- Supabase Security Advisor flagged with "Function Search Path Mutable".
-- An unset/mutable search_path lets a hostile role create objects in
-- `pg_temp` (or another reachable schema) and shadow references inside
-- the function body — particularly dangerous for SECURITY DEFINER
-- functions.
--
-- Why `''` (empty) is safe here: every reference inside these function
-- bodies is already fully schema-qualified — `public.case_assignments`,
-- `public.rfqs`, `public.admin_allowlist`, `public.hr_profiles`,
-- `public.recalculate_case_risk`, `auth.uid()`. Built-ins like `now()`,
-- `coalesce()`, `btrim()`, `jsonb_array_elements()`, casts, and
-- `exists(…)` resolve via the implicit `pg_catalog` lookup, which
-- Postgres always performs even when `pg_catalog` is not listed in
-- `search_path`. So an empty search_path is the strictest setting that
-- keeps current behaviour while closing the search-path attack surface.
--
-- Discovery via DO block instead of explicit `ALTER FUNCTION` per name:
-- some functions exist in production via legacy runtime DDL but aren't
-- recreated by the migration history (e.g. `try_parse_timestamptz`),
-- so a Supabase Branching preview that replays migrations from scratch
-- would fail on a hardcoded `ALTER FUNCTION` for those. The DO block
-- only ALTERs what actually exists and skips functions that already
-- have a `search_path` set, making it idempotent and tolerant of
-- preview-vs-prod schema drift.

DO $$
DECLARE
  fn        record;
  altered_n int := 0;
BEGIN
  FOR fn IN
    SELECT
      n.nspname AS schema_name,
      p.proname AS func_name,
      pg_get_function_identity_arguments(p.oid) AS args
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.proname IN (
        'set_updated_at',
        'set_company_updated_at',
        'try_parse_timestamptz',
        'is_admin',
        'my_company_id',
        'trigger_recalculate_risk_on_task',
        'trigger_recalculate_risk_on_budget',
        'hr_reopen_assignment',
        'employee_unsubmit_assignment',
        'create_rfq_with_items'
      )
      -- Skip functions that already have a search_path pinned. proconfig
      -- is null when no SET clause was applied; once we set it, this
      -- filter makes the migration a no-op on subsequent runs.
      AND (
        p.proconfig IS NULL
        OR NOT EXISTS (
          SELECT 1
          FROM unnest(p.proconfig) AS cfg
          WHERE cfg LIKE 'search_path=%'
        )
      )
  LOOP
    EXECUTE format(
      $sql$ALTER FUNCTION %I.%I(%s) SET search_path = ''$sql$,
      fn.schema_name, fn.func_name, fn.args
    );
    altered_n := altered_n + 1;
    RAISE NOTICE 'pin-search-path: %.%(%) → search_path=''''',
      fn.schema_name, fn.func_name, fn.args;
  END LOOP;

  RAISE NOTICE 'pin-search-path: % function(s) hardened', altered_n;
END $$;
