-- AIQ-1419 (TD-1) — INSEAD corridor Test-Drive campaign schema.
--
-- One idempotent migration for the whole campaign (single 🔴 Red gate). Creates:
--   • test_sessions    — one tester's run (dual synthetic accounts + corridor + lifecycle)
--   • survey_responses — one wide row per submitted survey (two GDPR consent booleans)
--   • funnel_events    — lightweight funnel log (invites/clicks precede any session)
-- and adds campaign / corridor_id / tester_segment stamp columns to public.feedback.
--
-- These are ADMIN-ONLY campaign-analytics tables — NOT company-scoped. corridor_id /
-- tester_segment / campaign are analytical slice dimensions, not tenant boundaries.
-- Survey + invite/click writes originate from a PUBLIC/unauthenticated context, so writes
-- go through the backend (service_role); anon is fully revoked; only admins can read.
-- RLS hard gate (CLAUDE.md) mirrors 20260818000000_feedback_status.sql: ENABLE RLS +
-- admin-read via public.is_admin() + service_role all + REVOKE ALL FROM anon.
--
-- Migration discipline: committed here; applied out-of-band + ledger reconciled before the
-- campaign (not applied on merge).
begin;

-- ── test_sessions ───────────────────────────────────────────────────────────
create table if not exists public.test_sessions (
  id               uuid        primary key default gen_random_uuid(),
  campaign         text        not null,
  corridor_id      text        not null,
  tester_segment   text        not null default 'prospect'
                               check (tester_segment in ('internal', 'prospect')),
  first_name_label text,                                  -- human label only; identity is synthetic
  hr_user_id       uuid        references auth.users(id) on delete set null,
  emp_user_id      uuid        references auth.users(id) on delete set null,
  hr_username      text,
  emp_username     text,
  status           text        not null default 'started'
                               check (status in ('started', 'completed')),
  started_at       timestamptz not null default now(),
  completed_at     timestamptz,
  created_at       timestamptz not null default now()
);
create index if not exists idx_test_sessions_campaign_corridor
  on public.test_sessions(campaign, corridor_id);
create index if not exists idx_test_sessions_status on public.test_sessions(status);

alter table public.test_sessions ENABLE ROW LEVEL SECURITY;
drop policy if exists test_sessions_admin_read on public.test_sessions;
CREATE POLICY test_sessions_admin_read on public.test_sessions
  for select to authenticated using (public.is_admin());
drop policy if exists test_sessions_service_all on public.test_sessions;
CREATE POLICY test_sessions_service_all on public.test_sessions
  for all to service_role using (true) with check (true);
REVOKE ALL on public.test_sessions from anon;

-- ── survey_responses ────────────────────────────────────────────────────────
-- One wide row per submitted survey. tester_name/email are the only real PII captured;
-- testimonial_consent + referral_consent are per-item GDPR consent (Q5 / Q7).
create table if not exists public.survey_responses (
  id                    uuid        primary key default gen_random_uuid(),
  session_id            uuid        references public.test_sessions(id) on delete set null,
  campaign              text,
  corridor_id           text,
  tester_segment        text        check (tester_segment in ('internal', 'prospect')),
  tester_name           text,
  tester_email          text,
  tester_company_role   text,
  tester_sector         text,
  q1_overall            integer     check (q1_overall between 1 and 5),
  q2_friction           text,
  q3_problem_fit        text        check (q3_problem_fit in ('yes', 'somewhat', 'no')),
  q3_why                text,
  q4_change             text,
  testimonial           text,
  testimonial_consent   boolean     not null default false,
  pilot_interest        text        check (pilot_interest in ('yes', 'maybe', 'no')),
  pilot_note            text,
  referral_name         text,
  referral_company_role text,
  referral_contact      text,
  referral_consent      boolean     not null default false,
  created_at            timestamptz not null default now()
);
create index if not exists idx_survey_responses_session on public.survey_responses(session_id);
create index if not exists idx_survey_responses_campaign_corridor
  on public.survey_responses(campaign, corridor_id);

alter table public.survey_responses ENABLE ROW LEVEL SECURITY;
drop policy if exists survey_responses_admin_read on public.survey_responses;
CREATE POLICY survey_responses_admin_read on public.survey_responses
  for select to authenticated using (public.is_admin());
drop policy if exists survey_responses_service_all on public.survey_responses;
CREATE POLICY survey_responses_service_all on public.survey_responses
  for all to service_role using (true) with check (true);
REVOKE ALL on public.survey_responses from anon;

-- ── funnel_events ───────────────────────────────────────────────────────────
-- Lightweight funnel log. event_type is free-text (known set below) so new steps don't
-- need a migration. session_id is NULLABLE — invite-sent / click precede provisioning.
-- Known event_type values: invite-sent, click, start, hr-handoff, intake-start,
-- roadmap-reached, vendor-selected, completed, surveyed, intro, pilot-interested.
create table if not exists public.funnel_events (
  id             uuid        primary key default gen_random_uuid(),
  event_type     text        not null,
  session_id     uuid        references public.test_sessions(id) on delete set null,
  campaign       text,
  corridor_id    text,
  tester_segment text,
  invite_token   text,                                    -- per-invite token / UTM for click attribution
  metadata       jsonb       not null default '{}'::jsonb,
  created_at     timestamptz not null default now()
);
create index if not exists idx_funnel_events_campaign_corridor_type
  on public.funnel_events(campaign, corridor_id, event_type);
create index if not exists idx_funnel_events_session on public.funnel_events(session_id);
create index if not exists idx_funnel_events_type_time on public.funnel_events(event_type, created_at);

alter table public.funnel_events ENABLE ROW LEVEL SECURITY;
drop policy if exists funnel_events_admin_read on public.funnel_events;
CREATE POLICY funnel_events_admin_read on public.funnel_events
  for select to authenticated using (public.is_admin());
drop policy if exists funnel_events_service_all on public.funnel_events;
CREATE POLICY funnel_events_service_all on public.funnel_events
  for all to service_role using (true) with check (true);
REVOKE ALL on public.funnel_events from anon;

-- ── feedback: campaign slice stamps (TD-9) ──────────────────────────────────
-- Nullable text stamps written by the feedback widget during a live test session. The
-- existing INSERT policy (with check auth.uid() = user_id) already covers new columns.
alter table public.feedback
  add column if not exists campaign       text,
  add column if not exists corridor_id    text,
  add column if not exists tester_segment text;

commit;

-- ── Rollback ─────────────────────────────────────────────────────────────────
-- alter table public.feedback
--   drop column if exists tester_segment,
--   drop column if exists corridor_id,
--   drop column if exists campaign;
-- drop table if exists public.funnel_events;
-- drop table if exists public.survey_responses;
-- drop table if exists public.test_sessions;
