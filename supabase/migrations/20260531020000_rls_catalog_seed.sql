-- SEC-RLSd (AIQ-661) — RLS for public-read catalog / seed tables.
--
-- These tables are pure reference / lookup data (country profiles, country
-- resources, requirements catalog). They are public-read BY DESIGN: anyone,
-- including anon, may SELECT; writes are locked to admins (admin_allowlist)
-- and service_role (which bypasses RLS).
--
-- NOTE on grants: the SEC-002 remediation revoked anon/authenticated table
-- privileges on these tables, and RLS was later enabled with NO policy
-- (deny-all). A SELECT policy alone is therefore inert — PostgREST also needs
-- a GRANT SELECT for the role to issue the query. We restore the grants here
-- so the public-read design intent actually works through the anon key.
--
-- Admin gating uses public.is_admin() (= auth.uid() IN admin_allowlist),
-- matching backend is_admin() semantics exactly.
--
-- Triaged OUT of this subtask (kept on supabase/rls_allowlist.txt with a
-- reason comment): compliance_reference_sources (server-only provenance),
-- catalog_employee_demand + catalog_scrape_quota (tenant-scoped → SEC-RLSe),
-- relocation_sources (per-case, FK relocation_cases → SEC-RLSa).

begin;

-- ============================================================================
-- Public-read catalog tables: SELECT for anon + authenticated, admin-only write
-- ============================================================================
do $$
declare
  tbl text;
  public_tables text[] := array[
    'country_events',
    'country_profiles',
    'country_resource_items',
    'country_resource_sections',
    'requirements_catalog',
    'requirement_items'
  ];
begin
  foreach tbl in array public_tables loop
    execute format('alter table public.%I enable row level security', tbl);

    -- Anyone (including anon) may read.
    execute format('drop policy if exists %I on public.%I', tbl || '_public_select', tbl);
    execute format(
      $f$create policy %I on public.%I for select to anon, authenticated using (true)$f$,
      tbl || '_public_select', tbl
    );

    -- Writes locked to admin / service_role only.
    execute format('drop policy if exists %I on public.%I', tbl || '_admin_write', tbl);
    execute format(
      $f$create policy %I on public.%I for all to authenticated
         using (public.is_admin()) with check (public.is_admin())$f$,
      tbl || '_admin_write', tbl
    );

    -- Restore the role-level privileges PostgREST needs (RLS still gates rows).
    execute format('grant select on public.%I to anon, authenticated', tbl);
    execute format('grant insert, update, delete on public.%I to authenticated', tbl);

    -- Defense in depth — anon explicitly stripped of write privileges.
    execute format('revoke insert, update, delete on public.%I from anon', tbl);
  end loop;
end $$;

-- ============================================================================
-- default_policy_templates: seed policy template. Read only by authenticated
-- HR/admin config flows (no anonymous use case → least privilege), admin write.
-- ============================================================================
alter table public.default_policy_templates enable row level security;

-- Drop the legacy over-permissive policy from 20260408 if it ever applies
-- (it granted writes to ANY authenticated user via `using (true)`).
drop policy if exists default_policy_templates_admin on public.default_policy_templates;

drop policy if exists default_policy_templates_auth_select on public.default_policy_templates;
create policy default_policy_templates_auth_select on public.default_policy_templates
  for select to authenticated using (true);

drop policy if exists default_policy_templates_admin_write on public.default_policy_templates;
create policy default_policy_templates_admin_write on public.default_policy_templates
  for all to authenticated
  using (public.is_admin()) with check (public.is_admin());

grant select on public.default_policy_templates to authenticated;
grant insert, update, delete on public.default_policy_templates to authenticated;

-- Not anon-readable: this is config-flow seed data, not a public lookup.
revoke select, insert, update, delete on public.default_policy_templates from anon;

commit;
