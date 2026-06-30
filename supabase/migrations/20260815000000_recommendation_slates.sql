-- [P2] recommendation_slates — persist the recommender's candidate slate.
--
-- Today the recommendation pipeline emits only COUNTS (analytics_events
-- `recommendations_generated`), so the ranked candidate set a user actually saw
-- is never stored. That makes learned supplier ranking data-blocked: there is no
-- "shown" side to pair against the "chosen" side (supplier_selected /
-- quote_accepted). This table closes that gap — one row per recommendation
-- response, holding the ranked item_ids + per-factor feature breakdown + scores
-- so the offline fitter (backend/scripts/fit_supplier_weights.py) can build
-- chosen-vs-shown training pairs.
--
-- Rows are written best-effort from the recommendations router emit sites; a
-- write failure never breaks the request. Contents are training/observability
-- data, so access mirrors ml_models: service-role write, admin-only read, anon
-- revoked (CLAUDE.md hard gate).

begin;

create table if not exists public.recommendation_slates (
  id             uuid primary key default gen_random_uuid(),
  case_id        text,
  assignment_id  text,
  company_id     text,
  category       text not null,
  segment        text,
  criteria_json  jsonb not null default '{}'::jsonb,
  items_json     jsonb not null default '[]'::jsonb,
  created_at     timestamptz not null default now()
);

create index if not exists idx_recommendation_slates_cat_seg
  on public.recommendation_slates (category, segment, created_at desc);
create index if not exists idx_recommendation_slates_case
  on public.recommendation_slates (case_id);
create index if not exists idx_recommendation_slates_created
  on public.recommendation_slates (created_at desc);

-- ── RLS (CLAUDE.md hard gate) ──────────────────────────────────────────────
alter table public.recommendation_slates enable row level security;

-- Admin-only read (training/observability data; may echo case criteria).
drop policy if exists recommendation_slates_admin_read on public.recommendation_slates;
create policy recommendation_slates_admin_read on public.recommendation_slates
  for select to authenticated
  using (public.is_admin());

-- Backend writer (service_role). Explicit all-policy; service_role also bypasses RLS.
drop policy if exists recommendation_slates_service_all on public.recommendation_slates;
create policy recommendation_slates_service_all on public.recommendation_slates
  for all to service_role
  using (true) with check (true);

-- Defense-in-depth: the anon key is shipped in the frontend bundle.
revoke all on public.recommendation_slates from anon;

commit;

-- ── Rollback ───────────────────────────────────────────────────────────────
-- drop policy if exists recommendation_slates_admin_read on public.recommendation_slates;
-- drop policy if exists recommendation_slates_service_all on public.recommendation_slates;
-- drop index if exists public.idx_recommendation_slates_cat_seg;
-- drop index if exists public.idx_recommendation_slates_case;
-- drop index if exists public.idx_recommendation_slates_created;
-- drop table if exists public.recommendation_slates;
