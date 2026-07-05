-- AUTH-PAGE-CONFIG-01 — public-read, admin-write platform config for the
-- /auth page's GlobeNetwork canvas visualization.
--
-- Single-row (singleton, id=1) config table. Read by the anonymous /auth
-- login/register screen — no ReloPass session token exists pre-login, so this
-- must be readable with zero authentication. Written only by ReloPass admins
-- from the Auth Page Design admin screen (/admin/auth-page-design).
--
-- Pattern mirrors the public-read catalog tables established in
-- 20260611112655_sec_prmpt_01_restrict_prompt_tables_to_admin.sql: SELECT open
-- to anon + authenticated (this table holds no PII — just numeric/hex visual
-- tuning knobs for a decorative canvas animation), writes locked to
-- public.is_admin() (= auth.uid() IN admin_allowlist), matching backend
-- require_admin() semantics.
--
-- NOTE (migration discipline, see CLAUDE.md): this file is created but NOT
-- applied. Applying to production is a manual/out-of-band step (operator-run
-- `supabase db push` or MCP apply_migration), after which the ledger is
-- reconciled per the "Ledger reconciliation" section of CLAUDE.md.

begin;

create table if not exists public.auth_page_config (
  id integer primary key default 1,
  config jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  updated_by uuid,
  constraint auth_page_config_singleton check (id = 1)
);

alter table public.auth_page_config enable row level security;

-- Anyone (including anon) may read — the /auth page renders before login.
drop policy if exists auth_page_config_public_select on public.auth_page_config;
create policy auth_page_config_public_select on public.auth_page_config
  for select to anon, authenticated using (true);

-- Writes locked to admin / service_role only.
drop policy if exists auth_page_config_admin_write on public.auth_page_config;
create policy auth_page_config_admin_write on public.auth_page_config
  for all to authenticated
  using (public.is_admin()) with check (public.is_admin());

-- Defense in depth (hard gate #3): revoke anon entirely first, then restore
-- only the SELECT privilege PostgREST needs for the public-read policy above
-- to actually work through the anon key (RLS still gates which rows).
revoke all on public.auth_page_config from anon;
grant select on public.auth_page_config to anon;

grant select, insert, update, delete on public.auth_page_config to authenticated;

commit;
