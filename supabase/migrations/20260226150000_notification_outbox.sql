-- Option 6C: Outbox table for email delivery (service-only)

create table if not exists public.notification_outbox (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  notification_id uuid null references public.notifications(id) on delete set null,
  user_id uuid not null,
  to_email text not null,
  type text not null,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'pending',
  last_error text null,
  sent_at timestamptz null
);

create index if not exists idx_notification_outbox_status_created
  on public.notification_outbox (status, created_at)
  where status = 'pending';

alter table public.notification_outbox enable row level security;

-- Service-only: revoke from anon/authenticated, grant to service_role
revoke all on public.notification_outbox from anon;
revoke all on public.notification_outbox from authenticated;
grant select, insert, update on public.notification_outbox to service_role;

comment on table public.notification_outbox is 'Email delivery queue. Processed by Edge Function (6C).';
