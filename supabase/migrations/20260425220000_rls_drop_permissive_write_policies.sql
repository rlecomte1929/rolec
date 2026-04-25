-- Drop RLS write policies that use the "always true" predicate
-- (`USING (true)` / `WITH CHECK (true)`) for INSERT / UPDATE / DELETE / ALL
-- operations. Resolves the 32 "RLS Policy Always True" warnings raised by
-- the Supabase Security Advisor.
--
-- Why dropping is safe:
--
--   * `service_role` and `postgres` roles have BYPASSRLS = true, so any
--     policy attached to them is redundant — they ignore RLS entirely.
--     The backend uses both (service_role via supabase-py admin client,
--     postgres via the connection pooler), so its writes continue to work.
--
--   * For policies attached to `public` / `authenticated`, the affected
--     tables (collaboration_*, crawl_*, freshness_*, staged_*,
--     review_queue_*, ops_notification*, document_change_events,
--     default_policy_templates, case_resource_preferences) are not hit
--     directly from the frontend — every code path in the FastAPI backend
--     for these tables uses `get_supabase_admin_client()` (service_role)
--     or SQLAlchemy through the pooler (postgres). Removing the
--     `qual = 'true'` policy therefore tightens the surface — anon and
--     authenticated end-users can no longer write to admin/infra tables
--     via the Data API even if they bypass the FastAPI layer.
--
-- Self-discovering DO block: any policy in `public` whose USING or
-- WITH CHECK is exactly `true` and whose command is INSERT / UPDATE /
-- DELETE / ALL is dropped. Idempotent.

DO $$
DECLARE
  pol       record;
  dropped_n int := 0;
BEGIN
  FOR pol IN
    SELECT
      schemaname,
      tablename,
      policyname,
      cmd,
      roles,
      qual,
      with_check
    FROM pg_policies
    WHERE schemaname = 'public'
      AND cmd IN ('INSERT', 'UPDATE', 'DELETE', 'ALL')
      AND (
        coalesce(qual, '')       = 'true'
        OR coalesce(with_check, '') = 'true'
      )
  LOOP
    EXECUTE format(
      'DROP POLICY IF EXISTS %I ON %I.%I',
      pol.policyname, pol.schemaname, pol.tablename
    );
    dropped_n := dropped_n + 1;
    RAISE NOTICE
      'rls-permissive-drop: dropped %.%(%) [cmd=% roles=%]',
      pol.schemaname, pol.tablename, pol.policyname, pol.cmd, pol.roles;
  END LOOP;

  RAISE NOTICE 'rls-permissive-drop: % polic(ies) dropped', dropped_n;
END $$;
