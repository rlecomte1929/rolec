-- Ledger reconciliation (prod-as-oracle): this migration was applied to prod on
-- 2026-06-11 via MCP apply_migration but never committed. SQL below is the exact
-- recovered statement from supabase_migrations.schema_migrations. Idempotent.

-- SEC-PRMPT-01: Restrict prompt_versions + prompt_routing SELECT to admin only
-- Deployed: 2026-06-11

-- Drop the overly-broad authenticated SELECT policies (qual = true)
DROP POLICY IF EXISTS prompt_routing_auth_select ON public.prompt_routing;
DROP POLICY IF EXISTS prompt_versions_auth_select ON public.prompt_versions;

-- Replace with admin-only SELECT policies
CREATE POLICY prompt_routing_auth_select ON public.prompt_routing
  FOR SELECT TO authenticated
  USING (is_admin());

CREATE POLICY prompt_versions_auth_select ON public.prompt_versions
  FOR SELECT TO authenticated
  USING (is_admin());

COMMENT ON TABLE public.prompt_versions IS
  'AI prompt library — admin read/write only. Do not grant SELECT to authenticated broadly.';
COMMENT ON TABLE public.prompt_routing IS
  'AI prompt routing rules — admin read/write only. Do not grant SELECT to authenticated broadly.';
