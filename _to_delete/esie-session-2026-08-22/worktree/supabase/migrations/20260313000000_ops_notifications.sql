-- Ops Notifications: internal admin notification and escalation system
-- Admin-only; integrates with review queue, freshness, crawl, change detection
begin;

create table if not exists public.ops_notifications (
  id uuid primary key default gen_random_uuid(),
  notification_type text not null,
  severity text not null default 'warning',
  status text not null default 'open',
  title text not null default '',
  message text,
  country_code text,
  city_name text,
  content_domain text,
  trust_tier text,
  related_queue_item_id uuid references public.review_queue_items(id) on delete set null,
  related_stale_signal_id text,
  related_change_event_id uuid references public.document_change_events(id) on delete set null,
  related_crawl_job_run_id uuid,
  related_schedule_id uuid references public.crawl_schedules(id) on delete set null,
  related_source_name text,
  related_live_resource_id uuid,
  related_live_event_id uuid,
  related_staged_candidate_type text,
  related_staged_candidate_id uuid,
  escalation_level int,
  priority_score int,
  triggered_at timestamptz not null default now(),
  last_retriggered_at timestamptz,
  acknowledged_at timestamptz,
  acknowledged_by_user_id text,
  resolved_at timestamptz,
  resolved_by_user_id text,
  suppressed_until timestamptz,
  dedupe_key text not null,
  payload_json jsonb default '{}',
  retrigger_count int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_ops_notifications_dedupe_open
  on public.ops_notifications(dedupe_key)
  where status in ('open', 'acknowledged');

create index if not exists idx_ops_notifications_status on public.ops_notifications(status);
create index if not exists idx_ops_notifications_severity on public.ops_notifications(severity);
create index if not exists idx_ops_notifications_type on public.ops_notifications(notification_type);
create index if not exists idx_ops_notifications_triggered on public.ops_notifications(triggered_at desc);
create index if not exists idx_ops_notifications_queue_item on public.ops_notifications(related_queue_item_id) where related_queue_item_id is not null;
create index if not exists idx_ops_notifications_country on public.ops_notifications(country_code);
create index if not exists idx_ops_notifications_suppressed on public.ops_notifications(suppressed_until) where suppressed_until is not null;

create table if not exists public.ops_notification_events (
  id uuid primary key default gen_random_uuid(),
  notification_id uuid not null references public.ops_notifications(id) on delete cascade,
  event_type text not null,
  actor_user_id text,
  details_json jsonb default '{}',
  created_at timestamptz not null default now()
);

create index if not exists idx_ops_notification_events_notification on public.ops_notification_events(notification_id);
create index if not exists idx_ops_notification_events_created on public.ops_notification_events(created_at desc);

alter table public.ops_notifications enable row level security;
alter table public.ops_notification_events enable row level security;
create policy "ops_notifications_admin" on public.ops_notifications for all using (true) with check (true);
create policy "ops_notification_events_admin" on public.ops_notification_events for all using (true) with check (true);

commit;
