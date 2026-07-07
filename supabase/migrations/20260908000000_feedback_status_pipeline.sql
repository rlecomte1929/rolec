-- 20260908000000_feedback_status_pipeline.sql
-- Shared pipeline-state model on feedback_status (manual lane + autopilot).
-- Additive + idempotent. dispatch_status had no CHECK; adds one after normalizing legacy values.
alter table public.feedback_status
  add column if not exists autonomy_tier   text,
  add column if not exists pr_url          text,
  add column if not exists pr_number       bigint,
  add column if not exists branch_name     text,
  add column if not exists triaged_at      timestamptz,
  add column if not exists spec_drafted_at timestamptz,
  add column if not exists dispatched_at   timestamptz,
  add column if not exists in_progress_at  timestamptz,
  add column if not exists deployed_at     timestamptz,
  add column if not exists done_at         timestamptz;

-- Normalize any legacy dispatch_status values into the canonical lifecycle.
update public.feedback_status set dispatch_status = 'new'           where dispatch_status = 'pending';
update public.feedback_status set dispatch_status = 'verify_failed' where dispatch_status = 'failed';

alter table public.feedback_status drop constraint if exists feedback_status_dispatch_status_ck;
alter table public.feedback_status add constraint feedback_status_dispatch_status_ck
  check (dispatch_status is null or dispatch_status in (
    'new','triaged','spec_drafted','dispatched','in_progress','in_review',
    'deployed','done','verify_failed','dismissed','wont_fix'));

alter table public.feedback_status drop constraint if exists feedback_status_autonomy_tier_ck;
alter table public.feedback_status add constraint feedback_status_autonomy_tier_ck
  check (autonomy_tier is null or autonomy_tier in ('green','yellow','red'));

-- feedback_status already has RLS enabled + admin_read/service_all policies + REVOKE anon
-- (20260818000000). Altering columns inherits that posture — no new table, no new gate.
