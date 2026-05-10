-- Review Queue: unified operational queue for staged candidates, changes, stale content
-- Admin-only; no auto-publish; integrates with staging, freshness, change detection
begin;

create table if not exists public.review_queue_items (
  id uuid primary key default gen_random_uuid(),
  queue_item_type text not null,
  status text not null default 'new',
  priority_score int not null default 0,
  priority_band text not null default 'medium',
  severity text,
  country_code text,
  city_name text,
  content_domain text,
  trust_tier text,
  title text not null default '',
  summary text,
  source_name text,
  source_url text,
  related_staged_resource_candidate_id uuid references public.staged_resource_candidates(id) on delete set null,
  related_staged_event_candidate_id uuid references public.staged_event_candidates(id) on delete set null,
  related_change_event_id uuid references public.document_change_events(id) on delete set null,
  related_live_resource_id uuid,
  related_live_event_id uuid,
  related_alert_id uuid references public.freshness_alerts(id) on delete set null,
  assigned_to_user_id text,
  assigned_by_user_id text,
  assigned_at timestamptz,
  due_at timestamptz,
  sla_target_at timestamptz,
  created_from_signal_type text,
  created_from_signal_id text,
  priority_reasons_json jsonb default '[]',
  context_json jsonb default '{}',
  notes text,
  resolution_summary text,
  resolved_at timestamptz,
  resolved_by_user_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_review_queue_status on public.review_queue_items(status);
create index if not exists idx_review_queue_priority on public.review_queue_items(priority_band, priority_score desc);
create index if not exists idx_review_queue_assigned on public.review_queue_items(assigned_to_user_id);
create index if not exists idx_review_queue_type on public.review_queue_items(queue_item_type);
create index if not exists idx_review_queue_country on public.review_queue_items(country_code);
create index if not exists idx_review_queue_created on public.review_queue_items(created_at desc);
create index if not exists idx_review_queue_due on public.review_queue_items(due_at) where status not in ('resolved', 'rejected', 'deferred');
create unique index if not exists idx_review_queue_staged_resource on public.review_queue_items(related_staged_resource_candidate_id) where related_staged_resource_candidate_id is not null and status not in ('resolved', 'rejected', 'deferred');
create unique index if not exists idx_review_queue_staged_event on public.review_queue_items(related_staged_event_candidate_id) where related_staged_event_candidate_id is not null and status not in ('resolved', 'rejected', 'deferred');
create unique index if not exists idx_review_queue_change on public.review_queue_items(related_change_event_id) where related_change_event_id is not null and status not in ('resolved', 'rejected', 'deferred');
create unique index if not exists idx_review_queue_live_resource on public.review_queue_items(related_live_resource_id) where related_live_resource_id is not null and status not in ('resolved', 'rejected', 'deferred');
create unique index if not exists idx_review_queue_live_event on public.review_queue_items(related_live_event_id) where related_live_event_id is not null and status not in ('resolved', 'rejected', 'deferred');

create table if not exists public.review_queue_activity_log (
  id uuid primary key default gen_random_uuid(),
  queue_item_id uuid not null references public.review_queue_items(id) on delete cascade,
  action_type text not null,
  actor_user_id text not null,
  previous_status text,
  new_status text,
  previous_assignee_id text,
  new_assignee_id text,
  note text,
  created_at timestamptz not null default now()
);

create index if not exists idx_review_queue_activity_item on public.review_queue_activity_log(queue_item_id);
create index if not exists idx_review_queue_activity_created on public.review_queue_activity_log(created_at desc);

alter table public.review_queue_items enable row level security;
alter table public.review_queue_activity_log enable row level security;
create policy "review_queue_items_admin" on public.review_queue_items for all using (true) with check (true);
create policy "review_queue_activity_admin" on public.review_queue_activity_log for all using (true) with check (true);

commit;
