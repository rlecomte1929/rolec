-- [P2] supplier_ranking_weights — learned per-segment scoring weights.
--
-- One append-only row per (service_category, segment) fit, "latest computed_at
-- wins" on read (mirrors supplier_cluster_cache). weights_json is the learned
-- per-factor weight map the offline fitter
-- (backend/scripts/fit_supplier_weights.py) produces from recommendation_slates
-- ⋈ selection events. The recommendation hot path reads the latest cell ONLY
-- when the SUPPLIER_LEARNED_WEIGHTS env flag is on (see
-- recommendations/weights.py::get_weights); with the flag off the table is never
-- read and rankings are byte-identical.
--
-- segment is the normalised destination city; the global (un-segmented) bucket
-- is stored under the literal '__global__'. Non-PII tuning metadata, but kept
-- admin-read / service-write to match ml_models (CLAUDE.md hard gate).

begin;

create table if not exists public.supplier_ranking_weights (
  id               uuid primary key default gen_random_uuid(),
  service_category text not null,
  segment          text not null,
  weights_json     jsonb not null,
  n_training_pairs int  not null default 0,
  model_kind       text not null default 'logistic_ltr',
  metadata_json    jsonb not null default '{}'::jsonb,
  computed_at      timestamptz not null default now()
);

create index if not exists idx_supplier_ranking_weights_cell_latest
  on public.supplier_ranking_weights (service_category, segment, computed_at desc);

-- ── RLS (CLAUDE.md hard gate) ──────────────────────────────────────────────
alter table public.supplier_ranking_weights enable row level security;

-- Admin-only read.
drop policy if exists supplier_ranking_weights_admin_read on public.supplier_ranking_weights;
create policy supplier_ranking_weights_admin_read on public.supplier_ranking_weights
  for select to authenticated
  using (public.is_admin());

-- Backend writer (service_role). Explicit all-policy; service_role also bypasses RLS.
drop policy if exists supplier_ranking_weights_service_all on public.supplier_ranking_weights;
create policy supplier_ranking_weights_service_all on public.supplier_ranking_weights
  for all to service_role
  using (true) with check (true);

-- Defense-in-depth: the anon key is shipped in the frontend bundle.
revoke all on public.supplier_ranking_weights from anon;

commit;

-- ── Rollback ───────────────────────────────────────────────────────────────
-- drop policy if exists supplier_ranking_weights_admin_read on public.supplier_ranking_weights;
-- drop policy if exists supplier_ranking_weights_service_all on public.supplier_ranking_weights;
-- drop index if exists public.idx_supplier_ranking_weights_cell_latest;
-- drop table if exists public.supplier_ranking_weights;
