-- Demo-request lead capture from the public landing pages.
-- Populated by the `submit-demo-request` Edge Function using the service role.
-- Never written or read directly by anon/authenticated clients.

create table if not exists public.demo_requests (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  first_name text not null,
  email text not null,
  company text not null,
  challenge text not null,
  source_page text null,
  user_agent text null,
  status text not null default 'new'
);

create index if not exists idx_demo_requests_created_at
  on public.demo_requests (created_at desc);

alter table public.demo_requests enable row level security;

revoke all on public.demo_requests from anon;
revoke all on public.demo_requests from authenticated;
grant select, insert, update on public.demo_requests to service_role;

comment on table public.demo_requests is
  'Demo booking leads submitted from public landing pages. Written by submit-demo-request Edge Function.';
