-- Analytics events for workflow observability (recommendations, supplier engagement, RFQ, quotes)
begin;

create table if not exists public.analytics_events (
  id uuid primary key default gen_random_uuid(),
  event_name text not null,
  payload_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_analytics_events_name on public.analytics_events(event_name);
create index if not exists idx_analytics_events_created on public.analytics_events(created_at);

-- RLS: service_role only (admin writes/reads via backend)
alter table public.analytics_events enable row level security;

-- No policies for authenticated - backend uses service_role for admin analytics
drop policy if exists analytics_events_admin on public.analytics_events;
create policy analytics_events_admin on public.analytics_events
  for all to service_role using (true) with check (true);

commit;
