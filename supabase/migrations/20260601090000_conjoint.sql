-- Parker Step H — Conjoint analysis on benefit preferences.
--
-- Three company-scoped tables backing a choice-based-conjoint (CBC) study:
--   conjoint_studies    — the study definition (attributes -> levels) per company.
--   conjoint_responses  — one row per respondent choice; respondents see only their own.
--   conjoint_results    — fitted part-worths + fit quality, recomputed on /fit.
--
-- Security (CLAUDE.md hard gate — all three tables):
--   * ENABLE ROW LEVEL SECURITY
--   * >=1 tenant-scoping policy (company HR via public.hr_company_ids(), admin carve-out
--     via public.is_admin(); respondents scoped to their own rows via auth.uid()).
--   * REVOKE ALL ... FROM anon.
--
-- NOT auto-applied. Per repo workflow, migrations are reviewed by a human and applied via
-- the Supabase MCP `apply_migration` (`supabase db push` is blocked by history drift).

begin;

-- ── conjoint_studies ─────────────────────────────────────────────────────────
create table if not exists public.conjoint_studies (
  id                uuid primary key default gen_random_uuid(),
  company_id        uuid not null references public.companies(id) on delete cascade,
  name              text,
  status            text not null default 'draft',
  attributes_json   jsonb,
  n_responses_target int not null default 100,
  opened_at         timestamptz,
  closed_at         timestamptz,
  created_at        timestamptz not null default now()
);
create index if not exists idx_conjoint_studies_company
  on public.conjoint_studies(company_id);

alter table public.conjoint_studies enable row level security;

drop policy if exists conjoint_studies_company_scoped on public.conjoint_studies;
create policy conjoint_studies_company_scoped on public.conjoint_studies
  for all to authenticated
  using (company_id::text in (select public.hr_company_ids()) or public.is_admin())
  with check (company_id::text in (select public.hr_company_ids()) or public.is_admin());

drop policy if exists conjoint_studies_service_all on public.conjoint_studies;
create policy conjoint_studies_service_all on public.conjoint_studies
  for all to service_role using (true) with check (true);

grant select, insert, update, delete on public.conjoint_studies to authenticated;
revoke all on public.conjoint_studies from anon;

-- ── conjoint_responses ───────────────────────────────────────────────────────
create table if not exists public.conjoint_responses (
  id                  uuid primary key default gen_random_uuid(),
  study_id            uuid not null references public.conjoint_studies(id) on delete cascade,
  respondent_user_id  uuid,
  choice_set_json     jsonb,
  choice_set_hash     text,
  chosen_index        int,
  responded_at        timestamptz not null default now()
);
create index if not exists idx_conjoint_responses_study
  on public.conjoint_responses(study_id);
-- One response per respondent per choice set (idempotent submit).
create unique index if not exists uq_conjoint_responses_dedup
  on public.conjoint_responses(study_id, respondent_user_id, choice_set_hash);

alter table public.conjoint_responses enable row level security;

-- Respondents may read / write only their own rows.
drop policy if exists conjoint_responses_own on public.conjoint_responses;
create policy conjoint_responses_own on public.conjoint_responses
  for all to authenticated
  using (respondent_user_id::text = (select auth.uid())::text)
  with check (respondent_user_id::text = (select auth.uid())::text);

-- Company HR / admin may READ responses (needed to fit). Aggregates only ever leave the
-- API — respondent_user_id is never returned to HR. No HR write path on responses.
drop policy if exists conjoint_responses_company_read on public.conjoint_responses;
create policy conjoint_responses_company_read on public.conjoint_responses
  for select to authenticated
  using (
    exists (
      select 1 from public.conjoint_studies s
      where s.id = conjoint_responses.study_id
        and (s.company_id::text in (select public.hr_company_ids()) or public.is_admin())
    )
  );

drop policy if exists conjoint_responses_service_all on public.conjoint_responses;
create policy conjoint_responses_service_all on public.conjoint_responses
  for all to service_role using (true) with check (true);

grant select, insert, update, delete on public.conjoint_responses to authenticated;
revoke all on public.conjoint_responses from anon;

-- ── conjoint_results ─────────────────────────────────────────────────────────
create table if not exists public.conjoint_results (
  id                uuid primary key default gen_random_uuid(),
  study_id          uuid not null references public.conjoint_studies(id) on delete cascade,
  part_worths_json  jsonb,
  fit_quality_json  jsonb,
  computed_at       timestamptz not null default now()
);
create index if not exists idx_conjoint_results_study
  on public.conjoint_results(study_id);

alter table public.conjoint_results enable row level security;

drop policy if exists conjoint_results_company_scoped on public.conjoint_results;
create policy conjoint_results_company_scoped on public.conjoint_results
  for all to authenticated
  using (
    exists (
      select 1 from public.conjoint_studies s
      where s.id = conjoint_results.study_id
        and (s.company_id::text in (select public.hr_company_ids()) or public.is_admin())
    )
  )
  with check (
    exists (
      select 1 from public.conjoint_studies s
      where s.id = conjoint_results.study_id
        and (s.company_id::text in (select public.hr_company_ids()) or public.is_admin())
    )
  );

drop policy if exists conjoint_results_service_all on public.conjoint_results;
create policy conjoint_results_service_all on public.conjoint_results
  for all to service_role using (true) with check (true);

grant select, insert, update, delete on public.conjoint_results to authenticated;
revoke all on public.conjoint_results from anon;

commit;
