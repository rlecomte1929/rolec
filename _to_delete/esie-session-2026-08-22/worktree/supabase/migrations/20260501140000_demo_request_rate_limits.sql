-- Rate-limit tracking for the submit-demo-request Edge Function.
-- Stores a SHA-256 hash of the submitter IP (not the raw IP) so we can cap
-- requests per IP per hour without retaining identifiable network data.

create table if not exists public.demo_request_rate_limits (
  id uuid primary key default gen_random_uuid(),
  ip_hash text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_demo_request_rate_limits_ip_time
  on public.demo_request_rate_limits (ip_hash, created_at desc);

alter table public.demo_request_rate_limits enable row level security;

revoke all on public.demo_request_rate_limits from anon;
revoke all on public.demo_request_rate_limits from authenticated;
grant select, insert, delete on public.demo_request_rate_limits to service_role;

comment on table public.demo_request_rate_limits is
  'Hashed-IP request log for submit-demo-request rate limiting. Service-role only; rows older than 1 hour are pruned by the Edge Function on each submission.';
