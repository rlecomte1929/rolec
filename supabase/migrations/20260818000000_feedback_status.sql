-- [Task-6] feedback_status — triage state for all feedback streams.
-- AI/ML source tables (feedback, ai_human_feedback, policy_answer_helpfulness)
-- are never mutated. Triage state lives here, keyed by (stream, source_id).
begin;

create table if not exists public.feedback_status (
  stream       text        not null,
  source_id    text        not null,
  status       text        not null default 'new'
                           check (status in ('new', 'reviewed', 'acted_on', 'closed')),
  owner        text,
  resolution   text,
  updated_at   timestamptz not null default now(),
  primary key (stream, source_id)
);

-- ── RLS (CLAUDE.md hard gate) ──────────────────────────────────────────────
alter table public.feedback_status enable row level security;

-- Admin-only read.
drop policy if exists feedback_status_admin_read on public.feedback_status;
create policy feedback_status_admin_read on public.feedback_status
  for select to authenticated
  using (public.is_admin());

-- Backend writer (service_role). Explicit all-policy; service_role also bypasses RLS.
drop policy if exists feedback_status_service_all on public.feedback_status;
create policy feedback_status_service_all on public.feedback_status
  for all to service_role
  using (true) with check (true);

-- Defense-in-depth: the anon key is shipped in the frontend bundle.
revoke all on public.feedback_status from anon;

commit;

-- ── Rollback ───────────────────────────────────────────────────────────────
-- drop policy if exists feedback_status_admin_read on public.feedback_status;
-- drop policy if exists feedback_status_service_all on public.feedback_status;
-- drop table if exists public.feedback_status;
