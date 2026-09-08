-- FOUNDATION-1A: analytics events + daily_summaries schema
-- Creates two tables for the ReloPass AI-legibility foundation:
--   • events          — append-only ledger of every platform interaction
--   • daily_summaries — AI-generated nightly digests over event aggregates
--
-- RLS: events is INSERT-only for authenticated users, SELECT/UPDATE/DELETE
--      locked to ADMIN role (or service-role via bypass). This makes the
--      table append-only from any auth'd client.

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. events table
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists public.events (
  id           uuid        primary key default gen_random_uuid(),
  created_at   timestamptz not null    default now(),

  -- What happened
  event_type   text        not null,   -- e.g. 'page_view', 'assignment_created'
  entity_type  text,                   -- e.g. 'assignment', 'case', 'policy'
  entity_id    text,                   -- UUID or slug of the affected entity

  -- Who did it (privacy-safe)
  user_id      text,                   -- SHA-256 hash of auth.uid(); never raw PII
  company_id   text,                   -- UUID of the HR company
  session_id   text,                   -- random session token from client

  -- How it arrived
  source       text        not null    -- 'web' | 'api' | 'agent' | 'scheduler'
               default 'web'
               check (source in ('web', 'api', 'agent', 'scheduler')),

  -- Event-specific payload (flexible JSONB)
  properties   jsonb       not null    default '{}'::jsonb
);

-- Composite index for the primary query pattern:
-- "all events for company X, of type Y, in time range Z"
create index if not exists events_company_type_time_idx
  on public.events (company_id, event_type, created_at desc);

-- Additional indexes for common lookups
create index if not exists events_entity_idx
  on public.events (entity_type, entity_id);

create index if not exists events_created_at_idx
  on public.events (created_at desc);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. RLS — append-only enforcement
-- ─────────────────────────────────────────────────────────────────────────────

alter table public.events enable row level security;

-- Authenticated users may insert their own events
create policy "events_insert_authenticated"
  on public.events for insert
  to authenticated
  with check (true);

-- Admins may read all events
create policy "events_select_admin"
  on public.events for select
  using (
    exists (
      select 1 from public.profiles
      where profiles.id::uuid = auth.uid()
        and profiles.role = 'ADMIN'
    )
  );

-- UPDATE and DELETE are intentionally omitted → no policy = no access
-- (append-only is enforced by the absence of UPDATE/DELETE policies)

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. daily_summaries table
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists public.daily_summaries (
  id             uuid        primary key default gen_random_uuid(),
  created_at     timestamptz not null    default now(),

  -- What day + what lens
  date           date        not null,
  summary_type   text        not null    -- 'user_behaviour' | 'assignments' | 'platform_health'
                 check (summary_type in ('user_behaviour', 'assignments', 'platform_health')),

  -- AI-generated digest
  summary_text   text        not null    default '',

  -- Aggregated raw counts for that day
  raw_counts     jsonb       not null    default '{}'::jsonb,

  -- Anomaly flags produced by the nightly job
  anomalies      jsonb       not null    default '[]'::jsonb,

  -- One row per (date, summary_type)
  unique (date, summary_type)
);

create index if not exists daily_summaries_date_idx
  on public.daily_summaries (date desc);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. RLS — daily_summaries
-- ─────────────────────────────────────────────────────────────────────────────

alter table public.daily_summaries enable row level security;

-- Admins can read all summaries
create policy "daily_summaries_select_admin"
  on public.daily_summaries for select
  using (
    exists (
      select 1 from public.profiles
      where profiles.id::uuid = auth.uid()
        and profiles.role = 'ADMIN'
    )
  );

-- Only service-role (Edge Functions) may insert/update summaries
-- No authenticated-client policy → inserts from client are blocked
-- (the nightly aggregation Edge Function uses service-role which bypasses RLS)
