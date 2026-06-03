-- MATCHING-5A: assignment_outcomes table + supplier_stats materialised view
-- Creates the data foundation for AI-driven supplier matching score feedback loop.
--
-- assignment_outcomes — one row per completed assignment, capturing quality/speed/
--   communication scores rated by HR. Append-only via RLS (no UPDATE/DELETE).
--
-- supplier_stats — materialised view aggregating per-supplier performance.
--   Refreshed nightly by the nightly-aggregation Edge Function (or on demand).

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. assignment_outcomes
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists public.assignment_outcomes (
  id                      uuid         primary key default gen_random_uuid(),
  created_at              timestamptz  not null    default now(),

  -- Which assignment and which supplier
  assignment_id           text         not null    references public.case_assignments(id),
  supplier_id             uuid         not null    references public.suppliers(id),

  -- Outcome quality ratings (1.00–5.00 scale, null = not yet rated)
  quality_score           numeric(3,2) check (quality_score between 1 and 5),
  speed_score             numeric(3,2) check (speed_score between 1 and 5),
  communication_score     numeric(3,2) check (communication_score between 1 and 5),

  -- Outcome facts
  completed_on_time       boolean,
  -- (actual_cost - budget) / budget * 100; negative = under budget
  budget_variance_pct     numeric(8,2),

  -- Free-text HR feedback for qualitative signal
  hr_feedback             text,

  -- Who rated it (SHA-256 of auth.uid() — never raw PII)
  rated_by                text,

  -- One outcome per assignment (a supplier is assigned once per assignment)
  unique (assignment_id)
);

-- Primary query pattern: "all outcomes for supplier X, ordered by recency"
create index if not exists assignment_outcomes_supplier_time_idx
  on public.assignment_outcomes (supplier_id, created_at desc);

-- Secondary lookup: "outcome for a specific assignment"
create index if not exists assignment_outcomes_assignment_idx
  on public.assignment_outcomes (assignment_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. RLS — assignment_outcomes
-- ─────────────────────────────────────────────────────────────────────────────

alter table public.assignment_outcomes enable row level security;

-- Admins can read all outcomes
create policy "outcomes_select_admin"
  on public.assignment_outcomes for select
  using (
    exists (
      select 1 from public.profiles
      where profiles.id::uuid = auth.uid()
        and profiles.role = 'ADMIN'
    )
  );

-- Authenticated users (HR) may insert outcomes
create policy "outcomes_insert_authenticated"
  on public.assignment_outcomes for insert
  to authenticated
  with check (true);

-- UPDATE and DELETE intentionally omitted → append-only

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. supplier_stats materialised view
-- ─────────────────────────────────────────────────────────────────────────────

create materialized view if not exists public.supplier_stats as
select
  s.id                                                              as supplier_id,
  s.name                                                            as supplier_name,

  -- Volume
  count(ao.id)                                                      as total_assignments,

  -- Quality dimensions (nullif guards against division by zero on 0-row suppliers)
  round(avg(ao.quality_score)::numeric, 2)                          as avg_quality_score,
  round(avg(ao.speed_score)::numeric, 2)                            as avg_speed_score,
  round(avg(ao.communication_score)::numeric, 2)                    as avg_communication_score,

  -- Composite score: equal-weight average of the three dimensions
  round(
    avg((ao.quality_score + ao.speed_score + ao.communication_score) / 3.0)::numeric,
    2
  )                                                                 as avg_overall_score,

  -- On-time delivery rate (0.0 – 1.0)
  round(
    (
      sum(case when ao.completed_on_time = true then 1 else 0 end)::numeric
      / nullif(count(ao.id), 0)
    )::numeric,
    4
  )                                                                 as on_time_rate,

  -- Budget discipline (negative = consistently under budget — good)
  round(avg(ao.budget_variance_pct)::numeric, 2)                   as avg_budget_variance_pct,

  -- Freshness
  max(ao.created_at)                                                as last_outcome_at

from public.suppliers s
left join public.assignment_outcomes ao on ao.supplier_id = s.id
group by s.id, s.name;

-- Unique index required for CONCURRENTLY refresh
create unique index if not exists supplier_stats_supplier_id_uidx
  on public.supplier_stats (supplier_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Refresh helper function (called by nightly-aggregation Edge Function)
-- ─────────────────────────────────────────────────────────────────────────────

create or replace function public.refresh_supplier_stats()
returns void
language sql
security definer
set search_path = public
as $$
  refresh materialized view concurrently public.supplier_stats;
$$;

-- Grant execute to service_role so the Edge Function can call it
grant execute on function public.refresh_supplier_stats() to service_role;
