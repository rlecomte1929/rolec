-- Corridor deadline-alert ledger.
--
-- The corridor step graphs (corridors/<ID>/pathways/*/v1.yaml) now carry an
-- opt-in `deadline_trigger` on steps that state a hard legal window. A sweep
-- (POST /api/crons/corridor-deadline-sweep) resolves each open case through the
-- existing scheduler, finds the steps whose alert window contains today, and
-- emits one notification_outbox row per firing.
--
-- This table is what makes that exactly-once. It mirrors the AIQ-656
-- case_milestone_reminders pattern (service-only, PK = the idempotency key).
--
-- Why the key is (case, step, due_date):
--   * case + step alone would fire once and never again, even after the move
--     date — and therefore the statutory deadline — moved. That is a real missed
--     obligation, not a duplicate suppressed.
--   * including the SEND date instead of the due date would re-fire daily for
--     the whole window.
-- The due date is the obligation's identity, so it belongs in the key.
--
-- A failure is RECORDED, never dropped: status 'no_contact' (no resolvable
-- recipient) and 'error' (emit failed) are rows, so an operator can see what did
-- not reach anyone. A silent skip is indistinguishable from a healthy quiet day.

begin;

create table if not exists public.corridor_deadline_events (
  -- '<case_ref>|<step_id>|<due_date>' — the idempotency key, and the PK so the
  -- database enforces exactly-once rather than the application remembering to.
  event_uid      text        primary key,

  case_ref       text        not null,
  corridor_id    text        not null,
  step_id        text        not null,          -- IMMUTABLE: renaming it re-fires history
  tag_name       text        not null,
  jurisdiction   text,                          -- ISO3 rule-set owner, audit only

  due_date       date        not null,
  trigger_date   date        not null,          -- due_date - lead_days
  lead_days      integer     not null,
  fired_on       date        not null,          -- the sweep's `today`

  status         text        not null
                 check (status in ('fired', 'no_contact', 'error')),
  channel        text        not null,
  recipient      text,                          -- email actually used (audit)
  detail         text,                          -- skip reason / error text

  created_at     timestamptz not null default now()
);

-- The operator view: what failed to reach anyone, most recent first.
create index if not exists idx_corridor_deadline_events_status
  on public.corridor_deadline_events (status, created_at desc)
  where status in ('no_contact', 'error');

-- Per-case history, for the case timeline and for debugging a "why did I get
-- this twice" report.
create index if not exists idx_corridor_deadline_events_case
  on public.corridor_deadline_events (case_ref, due_date);

-- ── RLS hard-gates (CLAUDE.md): service-only, like case_milestone_reminders ──
alter table public.corridor_deadline_events enable row level security;

drop policy if exists corridor_deadline_events_service_all
  on public.corridor_deadline_events;
create policy corridor_deadline_events_service_all
  on public.corridor_deadline_events
  for all to service_role
  using (true) with check (true);

revoke all on public.corridor_deadline_events from anon;
revoke all on public.corridor_deadline_events from authenticated;
grant select, insert on public.corridor_deadline_events to service_role;

comment on table public.corridor_deadline_events is
  'Exactly-once ledger for corridor deadline alerts. One row per (case, step, due_date). Written by POST /api/crons/corridor-deadline-sweep. Failures are rows (no_contact/error), never silent skips.';

commit;

-- ── pg_cron schedule (run once after deployment; mirrors milestone-reminders) ──
-- Daily. The job is idempotent, so the cadence only bounds alert latency.
--   SELECT cron.schedule(
--     'corridor-deadline-sweep',
--     '0 7 * * *',
--     $$
--       SELECT net.http_post(
--         url     := 'https://api.relopass.com/api/crons/corridor-deadline-sweep',
--         headers := '{"Authorization": "Bearer <CRON_SECRET>"}'::jsonb,
--         body    := '{}'::jsonb
--       )
--     $$
--   );
