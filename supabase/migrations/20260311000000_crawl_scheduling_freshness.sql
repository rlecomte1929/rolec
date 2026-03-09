-- Crawl scheduling, job runs, change detection, freshness monitoring
-- Backend-only; no auto-publish; admin governance preserved
begin;

-- 1. crawl_schedules: recurring crawl plans
create table if not exists public.crawl_schedules (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  is_active boolean not null default true,
  schedule_type text not null default 'cron', -- cron, interval
  schedule_expression text not null, -- cron string or interval hours as text
  source_scope_type text not null, -- source, country, city, domain_group, source_group
  source_scope_ref text, -- source_name, country_code, etc.
  country_code text,
  city_name text,
  content_domain text,
  priority int not null default 0,
  max_runtime_seconds int,
  retry_policy_json jsonb default '{"max_retries": 2, "backoff_seconds": 60}',
  last_run_at timestamptz,
  next_run_at timestamptz,
  created_by_user_id text,
  updated_by_user_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_crawl_schedules_active_next on public.crawl_schedules(is_active, next_run_at) where is_active = true;

-- 2. crawl_job_runs: tracks each scheduled or manual run
create table if not exists public.crawl_job_runs (
  id uuid primary key default gen_random_uuid(),
  schedule_id uuid references public.crawl_schedules(id) on delete set null,
  crawl_run_id uuid references public.crawl_runs(id) on delete set null, -- links to actual crawl_runs
  job_type text not null, -- crawl_source, crawl_source_group, crawl_country_city_scope, extract_from_existing_documents, refresh_change_detection, refresh_freshness_metrics
  trigger_type text not null default 'manual', -- scheduled, manual, retry, backfill
  status text not null default 'queued', -- queued, running, succeeded, failed, cancelled, partial_success
  started_at timestamptz,
  finished_at timestamptz,
  requested_by_user_id text,
  scope_json jsonb default '{}',
  config_snapshot_json jsonb default '{}',
  documents_fetched_count int,
  documents_changed_count int,
  documents_unchanged_count int,
  chunks_created_count int,
  staged_resources_count int,
  staged_events_count int,
  warnings_count int,
  errors_count int,
  summary_json jsonb default '{}',
  error_summary text,
  lock_until timestamptz, -- for concurrency control
  created_at timestamptz not null default now()
);

create index if not exists idx_crawl_job_runs_status on public.crawl_job_runs(status);
create index if not exists idx_crawl_job_runs_schedule on public.crawl_job_runs(schedule_id);
create index if not exists idx_crawl_job_runs_started on public.crawl_job_runs(started_at desc);

-- 3. document_change_events: detected changes per document
create table if not exists public.document_change_events (
  id uuid primary key default gen_random_uuid(),
  job_run_id uuid references public.crawl_job_runs(id) on delete cascade,
  crawl_run_id uuid references public.crawl_runs(id) on delete set null,
  source_document_id uuid references public.crawled_source_documents(id) on delete set null,
  source_url text not null,
  source_name text not null,
  country_code text,
  city_name text,
  previous_document_id uuid references public.crawled_source_documents(id) on delete set null,
  previous_content_hash text,
  new_content_hash text not null,
  change_type text not null, -- new, updated, removed, unchanged, significant_change, minor_change
  change_score numeric, -- 0-1, higher = more significant
  diff_summary_json jsonb default '{}',
  detected_at timestamptz not null default now()
);

create index if not exists idx_doc_change_events_run on public.document_change_events(job_run_id);
create index if not exists idx_doc_change_events_source on public.document_change_events(source_name, source_url);
create index if not exists idx_doc_change_events_detected on public.document_change_events(detected_at desc);

-- 4. freshness_snapshots: aggregated freshness metrics
create table if not exists public.freshness_snapshots (
  id uuid primary key default gen_random_uuid(),
  snapshot_scope_type text not null, -- global, country, city, source, content_domain
  country_code text,
  city_name text,
  source_name text,
  content_domain text,
  captured_at timestamptz not null default now(),
  fresh_sources_count int not null default 0,
  stale_sources_count int not null default 0,
  overdue_sources_count int not null default 0,
  documents_changed_recently_count int not null default 0,
  live_resources_stale_count int not null default 0,
  live_events_expired_count int not null default 0,
  needs_review_candidates_count int not null default 0,
  metrics_json jsonb default '{}'
);

create index if not exists idx_freshness_snapshots_scope on public.freshness_snapshots(snapshot_scope_type, country_code, city_name, source_name);
create index if not exists idx_freshness_snapshots_captured on public.freshness_snapshots(captured_at desc);

-- 5. freshness_alerts: actionable alerts for admin
create table if not exists public.freshness_alerts (
  id uuid primary key default gen_random_uuid(),
  alert_type text not null, -- source_overdue, significant_change, live_content_stale, low_coverage, crawl_failure
  severity text not null default 'medium', -- low, medium, high
  scope_type text, -- source, country, city
  country_code text,
  city_name text,
  source_name text,
  related_schedule_id uuid references public.crawl_schedules(id) on delete set null,
  related_job_run_id uuid references public.crawl_job_runs(id) on delete set null,
  related_live_resource_id uuid,
  related_live_event_id uuid,
  status text not null default 'open', -- open, acknowledged, resolved
  title text not null,
  message text,
  payload_json jsonb default '{}',
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create index if not exists idx_freshness_alerts_status on public.freshness_alerts(status);
create index if not exists idx_freshness_alerts_created on public.freshness_alerts(created_at desc);

-- 6. document_url_index: for change detection - latest doc per (source_name, url)
-- We query crawled_source_documents by source_name + final_url to find previous version
-- No new table; use existing crawled_source_documents with composite query

-- RLS
alter table public.crawl_schedules enable row level security;
alter table public.crawl_job_runs enable row level security;
alter table public.document_change_events enable row level security;
alter table public.freshness_snapshots enable row level security;
alter table public.freshness_alerts enable row level security;

create policy "crawl_schedules_admin" on public.crawl_schedules for all using (true) with check (true);
create policy "crawl_job_runs_admin" on public.crawl_job_runs for all using (true) with check (true);
create policy "document_change_events_admin" on public.document_change_events for all using (true) with check (true);
create policy "freshness_snapshots_admin" on public.freshness_snapshots for all using (true) with check (true);
create policy "freshness_alerts_admin" on public.freshness_alerts for all using (true) with check (true);

-- Index for finding previous document by source+url (for change detection)
create index if not exists idx_crawled_docs_source_url on public.crawled_source_documents(source_name, coalesce(final_url, source_url));

commit;
