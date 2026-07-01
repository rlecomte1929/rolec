-- [Admin-hardening Task 3] platform_settings — env→DB→default resolver store.
--
-- One row per setting key; the backend resolver (backend/app/services/platform_settings.py)
-- reads this table ONLY when the env-var override is absent, so env always wins.
-- The table may not exist pre-migration; the resolver is best-effort and falls
-- through to its ``default`` argument, guaranteeing no behaviour change until an
-- admin explicitly writes a row.
--
-- admin-read / service-write mirrors supplier_ranking_weights (CLAUDE.md hard gate).

begin;

create table if not exists public.platform_settings (
  key         text        primary key,
  value_json  jsonb       not null,
  updated_by  text,
  updated_at  timestamptz not null default now()
);

-- ── RLS (CLAUDE.md hard gate) ──────────────────────────────────────────────
alter table public.platform_settings enable row level security;

-- Admin-only read.
drop policy if exists platform_settings_admin_read on public.platform_settings;
create policy platform_settings_admin_read on public.platform_settings
  for select to authenticated
  using (public.is_admin());

-- Backend writer (service_role). Explicit all-policy; service_role also bypasses RLS.
drop policy if exists platform_settings_service_all on public.platform_settings;
create policy platform_settings_service_all on public.platform_settings
  for all to service_role
  using (true) with check (true);

-- Defense-in-depth: the anon key is shipped in the frontend bundle.
revoke all on public.platform_settings from anon;

commit;

-- ── Rollback ───────────────────────────────────────────────────────────────
-- drop policy if exists platform_settings_admin_read on public.platform_settings;
-- drop policy if exists platform_settings_service_all on public.platform_settings;
-- drop table if exists public.platform_settings;
