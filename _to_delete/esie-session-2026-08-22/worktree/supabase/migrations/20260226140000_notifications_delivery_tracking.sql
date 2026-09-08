-- Option 6C: Delivery tracking columns on notifications (nullable, safe migration)

alter table public.notifications
  add column if not exists email_status text null,
  add column if not exists email_last_error text null,
  add column if not exists delivered_at timestamptz null,
  add column if not exists source text null,
  add column if not exists priority int null default 0;

create index if not exists idx_notifications_email_status
  on public.notifications (email_status)
  where email_status is not null;

comment on column public.notifications.email_status is 'pending|sent|failed for email delivery';
comment on column public.notifications.source is 'app|rpc|trigger';
