-- ============================================================================
-- Parker-B · Benefit-mix optimizer priors  (benefit_priors)
-- ============================================================================
-- Admin-seeded priors (expected satisfaction + variance) per company / benefit,
-- consumed by the Markowitz-style optimizer behind
-- POST /api/hr/{company_id}/optimize-benefit-mix.
--
-- Security (CLAUDE.md hard gate — new public table):
--   * RLS enabled.
--   * Company-scoped policy reusing public.hr_company_ids() (the canonical HR
--     membership helper from the SEC-RLSb policy/HR-domain migration) plus a
--     public.is_admin() carve-out for the CMS.
--   * Explicit service_role ALL policy (backend FastAPI path).
--   * REVOKE ALL ... FROM anon (defense-in-depth — the anon key ships in the
--     frontend bundle and PostgREST exposes the public schema).
--
-- Rollback block is at the bottom of this file.
-- ============================================================================

begin;

create table if not exists public.benefit_priors (
    id                     uuid primary key default gen_random_uuid(),
    company_id             uuid not null references public.companies(id) on delete cascade,
    category               text not null,
    attr_key               text not null,
    expected_satisfaction  numeric not null,
    variance               numeric,
    source                 text default 'admin_seed',
    updated_at             timestamptz not null default now(),
    updated_by             uuid references public.profiles(id) on delete set null,
    constraint benefit_priors_company_cat_attr_uniq unique (company_id, category, attr_key)
);

create index if not exists benefit_priors_company_idx
    on public.benefit_priors (company_id);

-- ── RLS ─────────────────────────────────────────────────────────────────────
alter table public.benefit_priors enable row level security;

drop policy if exists benefit_priors_company_scoped on public.benefit_priors;
create policy benefit_priors_company_scoped on public.benefit_priors
    for all
    to authenticated
    using (
        company_id::text in (select public.hr_company_ids())
        or public.is_admin()
    )
    with check (
        company_id::text in (select public.hr_company_ids())
        or public.is_admin()
    );

drop policy if exists benefit_priors_service_all on public.benefit_priors;
create policy benefit_priors_service_all on public.benefit_priors
    for all
    to service_role
    using (true)
    with check (true);

revoke all on public.benefit_priors from anon;

commit;

-- ============================================================================
-- ROLLBACK (manual):
--   begin;
--   drop policy if exists benefit_priors_company_scoped on public.benefit_priors;
--   drop policy if exists benefit_priors_service_all on public.benefit_priors;
--   drop table if exists public.benefit_priors;
--   commit;
-- ============================================================================
