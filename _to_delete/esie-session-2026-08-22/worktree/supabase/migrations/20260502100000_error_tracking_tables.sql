-- Error tracking foundation: raw events + grouped tickets.
-- Phase 1 — captures errors reported from the frontend via the
-- capture-error Edge Function, deduplicated by fingerprint.

-- error_logs: one row per error event received from the frontend
create table if not exists public.error_logs (
  id              uuid        primary key default gen_random_uuid(),
  fingerprint     text        not null,
  message         text        not null,
  stack           text,
  url             text,
  user_id         uuid        references auth.users(id) on delete set null,
  component_name  text,
  browser         text,
  breadcrumbs     jsonb       not null default '[]'::jsonb,
  severity        text        not null default 'error'
                              check (severity in ('error', 'warning')),
  created_at      timestamptz not null default now()
);

create index if not exists error_logs_fingerprint_idx
  on public.error_logs(fingerprint);
create index if not exists error_logs_created_at_idx
  on public.error_logs(created_at desc);

-- error_tickets: one row per unique fingerprint (grouped issues)
create table if not exists public.error_tickets (
  id            uuid        primary key default gen_random_uuid(),
  fingerprint   text        unique not null,
  message       text        not null,
  first_seen    timestamptz not null default now(),
  last_seen     timestamptz not null default now(),
  event_count   integer     not null default 1,
  status        text        not null default 'open'
                            check (status in ('open', 'in_progress', 'resolved')),
  notes         text,
  resolved_at   timestamptz,
  created_at    timestamptz not null default now()
);

create index if not exists error_tickets_status_idx
  on public.error_tickets(status);
create index if not exists error_tickets_last_seen_idx
  on public.error_tickets(last_seen desc);

-- RLS: service-role inserts (Edge Function) bypass RLS. Admin SELECT/UPDATE only.
alter table public.error_logs    enable row level security;
alter table public.error_tickets enable row level security;

create policy "admin can read error_logs"
  on public.error_logs for select
  using (
    exists (
      select 1 from public.profiles
      where profiles.id = auth.uid()::text
        and profiles.role = 'ADMIN'
    )
  );

create policy "admin can read error_tickets"
  on public.error_tickets for select
  using (
    exists (
      select 1 from public.profiles
      where profiles.id = auth.uid()::text
        and profiles.role = 'ADMIN'
    )
  );

create policy "admin can update error_tickets"
  on public.error_tickets for update
  using (
    exists (
      select 1 from public.profiles
      where profiles.id = auth.uid()::text
        and profiles.role = 'ADMIN'
    )
  );
