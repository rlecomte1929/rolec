-- AIQ-656: event-driven case reminders (D-7 / D-3 / D-0) for case_milestones.
-- Replaces the AIQ-34-D cron design. A backend cron endpoint
-- (POST /api/crons/milestone-reminders) scans case_milestones for target_date
-- offsets and writes notification_outbox rows. This table provides exact
-- idempotency (criterion: "key = milestone_id + offset") via the composite PK.

begin;

-- Idempotency ledger: one row per (milestone, day-offset) that has fired.
create table if not exists public.case_milestone_reminders (
  milestone_id      uuid not null references public.case_milestones(id) on delete cascade,
  day_offset        int  not null,            -- 7, 3, or 0 (days before target_date)
  recipient_user_id text,                     -- who it was sent to (audit)
  to_email          text,                     -- email used (audit)
  sent_at           timestamptz not null default now(),
  primary key (milestone_id, day_offset)
);

create index if not exists idx_case_milestone_reminders_sent_at
  on public.case_milestone_reminders (sent_at);

-- Speeds up the per-offset scan: WHERE target_date = :d AND status NOT IN (...).
create index if not exists idx_case_milestones_target_date
  on public.case_milestones (target_date, status);

-- ── RLS hard-gates (CLAUDE.md): service-only, like notification_outbox ──
alter table public.case_milestone_reminders enable row level security;

drop policy if exists case_milestone_reminders_service_all on public.case_milestone_reminders;
create policy case_milestone_reminders_service_all
  on public.case_milestone_reminders
  for all to service_role
  using (true) with check (true);

revoke all on public.case_milestone_reminders from anon;
revoke all on public.case_milestone_reminders from authenticated;
grant select, insert, delete on public.case_milestone_reminders to service_role;

comment on table public.case_milestone_reminders is
  'AIQ-656 idempotency ledger for milestone D-7/D-3/D-0 reminders. One row per (milestone_id, day_offset). Written by POST /api/crons/milestone-reminders.';

commit;

-- ── pg_cron schedule (run once after deployment; mirrors deadline-reminder) ──
-- Hourly tick; the job is idempotent so the cadence only bounds latency.
--   SELECT cron.schedule(
--     'milestone-reminders',
--     '0 * * * *',
--     $$
--       SELECT net.http_post(
--         url     := 'https://api.relopass.com/api/crons/milestone-reminders',
--         headers := '{"Authorization": "Bearer <CRON_SECRET>"}'::jsonb,
--         body    := '{}'::jsonb
--       )
--     $$
--   );
