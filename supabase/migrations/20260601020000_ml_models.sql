-- Parker-A — ml_models: cache for trained ML model blobs (Cox case-duration model).
--
-- Holds pickled, version-tagged model artifacts written by the backend training
-- CLI running as the Supabase service_role. Read access is admin-only; the anon
-- key (shipped in the frontend bundle) must never see model internals or the
-- training-row counts. Follows the CLAUDE.md hard gate: RLS on, at least one
-- policy, REVOKE ALL FROM anon.
--
-- Admin gating uses public.is_admin() (= auth.uid() IN admin_allowlist), matching
-- the cases / policy-HR domain RLS migrations. There are deliberately NO
-- INSERT/UPDATE/DELETE policies for `authenticated`: only service_role writes
-- (and service_role bypasses RLS via the explicit all-policy below).

begin;

create table if not exists public.ml_models (
  id              uuid primary key default gen_random_uuid(),
  model_key       text not null,
  version         text not null,
  pickled_blob    bytea,
  trained_at      timestamptz not null default now(),
  n_training_rows int,
  concordance     numeric,
  status          text not null default 'active',
  metadata        jsonb not null default '{}'::jsonb
);

create index if not exists idx_ml_models_key_version
  on public.ml_models (model_key, version);
create index if not exists idx_ml_models_key_trained
  on public.ml_models (model_key, trained_at desc);

alter table public.ml_models enable row level security;

-- Admin CMS read-only access.
drop policy if exists ml_models_admin_read on public.ml_models;
create policy ml_models_admin_read on public.ml_models
  for select to authenticated
  using (public.is_admin());

-- Backend writer (service_role). Explicit all-policy mirrors the canonical
-- case_milestones pattern; service_role also bypasses RLS.
drop policy if exists ml_models_service_all on public.ml_models;
create policy ml_models_service_all on public.ml_models
  for all to service_role
  using (true) with check (true);

-- Defense-in-depth: the public anon role gets nothing.
revoke all on public.ml_models from anon;

commit;
