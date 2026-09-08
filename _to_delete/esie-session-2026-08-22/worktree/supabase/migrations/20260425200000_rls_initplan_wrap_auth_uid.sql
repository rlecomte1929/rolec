-- Wrap `auth.uid()` / `auth.jwt()` calls in RLS policies in `(select ...)` so
-- PostgreSQL evaluates them once per query (initplan cache) instead of once
-- per row. Resolves the 71+ `auth_rls_initplan` performance advisor warnings
-- on tables including `policy_configs`, `policy_config_versions`,
-- `policy_config_benefits`, `company_policies`, `case_services`, etc. — the
-- same tables behind the HR dashboard endpoints that were timing out.
--
-- This is a self-discovering migration: it walks `pg_policies`, finds every
-- policy that calls `auth.uid()` / `auth.jwt()` directly (i.e. not already
-- wrapped in a SELECT), and rewrites it. Behaviour is unchanged — only the
-- planner shape changes. Safe to re-run; only policies that still match the
-- bare-call pattern are touched.

DO $$
DECLARE
  pol         record;
  new_qual    text;
  new_check   text;
  roles_list  text;
  sql         text;
  rewrote_n   int := 0;
BEGIN
  FOR pol IN
    SELECT
      schemaname,
      tablename,
      policyname,
      permissive,
      cmd,
      roles,
      qual,
      with_check
    FROM pg_policies
    WHERE schemaname = 'public'
      AND (
        qual       ~ 'auth\.(uid|jwt|role)\s*\(\s*\)'
        OR with_check ~ 'auth\.(uid|jwt|role)\s*\(\s*\)'
      )
      -- Skip policies whose every auth.* call is already wrapped in (select …).
      AND (
        (qual       IS NOT NULL AND qual       ~ 'auth\.(uid|jwt|role)\s*\(\s*\)' AND qual       !~* '\(\s*select\s+auth\.(uid|jwt|role)\s*\(\s*\)\s*\)')
        OR
        (with_check IS NOT NULL AND with_check ~ 'auth\.(uid|jwt|role)\s*\(\s*\)' AND with_check !~* '\(\s*select\s+auth\.(uid|jwt|role)\s*\(\s*\)\s*\)')
      )
  LOOP
    new_qual  := pol.qual;
    new_check := pol.with_check;

    IF new_qual IS NOT NULL THEN
      new_qual := regexp_replace(new_qual, 'auth\.uid\s*\(\s*\)',  '(select auth.uid())',  'g');
      new_qual := regexp_replace(new_qual, 'auth\.jwt\s*\(\s*\)',  '(select auth.jwt())',  'g');
      new_qual := regexp_replace(new_qual, 'auth\.role\s*\(\s*\)', '(select auth.role())', 'g');
      -- Idempotency: undo the case where we just wrapped an already-wrapped call.
      new_qual := regexp_replace(new_qual, '\(select\s+\(select\s+auth\.(uid|jwt|role)\(\)\)\)', '(select auth.\1())', 'g');
    END IF;

    IF new_check IS NOT NULL THEN
      new_check := regexp_replace(new_check, 'auth\.uid\s*\(\s*\)',  '(select auth.uid())',  'g');
      new_check := regexp_replace(new_check, 'auth\.jwt\s*\(\s*\)',  '(select auth.jwt())',  'g');
      new_check := regexp_replace(new_check, 'auth\.role\s*\(\s*\)', '(select auth.role())', 'g');
      new_check := regexp_replace(new_check, '\(select\s+\(select\s+auth\.(uid|jwt|role)\(\)\)\)', '(select auth.\1())', 'g');
    END IF;

    -- Nothing changed (defensive): skip.
    IF coalesce(new_qual, '')  IS NOT DISTINCT FROM coalesce(pol.qual, '')
       AND coalesce(new_check, '') IS NOT DISTINCT FROM coalesce(pol.with_check, '') THEN
      CONTINUE;
    END IF;

    roles_list := array_to_string(ARRAY(
      SELECT quote_ident(r) FROM unnest(pol.roles::name[]) r
    ), ', ');

    EXECUTE format(
      'DROP POLICY IF EXISTS %I ON %I.%I',
      pol.policyname, pol.schemaname, pol.tablename
    );

    sql := format(
      'CREATE POLICY %I ON %I.%I AS %s FOR %s TO %s',
      pol.policyname,
      pol.schemaname,
      pol.tablename,
      CASE WHEN pol.permissive = 'PERMISSIVE' THEN 'PERMISSIVE' ELSE 'RESTRICTIVE' END,
      pol.cmd,
      roles_list
    );

    IF pol.qual IS NOT NULL THEN
      sql := sql || format(' USING (%s)', new_qual);
    END IF;
    IF pol.with_check IS NOT NULL THEN
      sql := sql || format(' WITH CHECK (%s)', new_check);
    END IF;

    EXECUTE sql;

    rewrote_n := rewrote_n + 1;
    RAISE NOTICE 'rls-initplan: rewrote %.%(%) [cmd=%]',
      pol.schemaname, pol.tablename, pol.policyname, pol.cmd;
  END LOOP;

  RAISE NOTICE 'rls-initplan: % polic(ies) rewrapped', rewrote_n;
END $$;
