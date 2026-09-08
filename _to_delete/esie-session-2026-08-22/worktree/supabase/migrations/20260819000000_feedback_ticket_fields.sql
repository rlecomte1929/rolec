-- [D-BugRoutine Slice-1] ticket fields on feedback_status.
--
-- Adds severity, area, reporter_id, dispatch_ref, dispatch_status to the
-- feedback_status table created by 20260818000000_feedback_status.sql.
-- All additions are idempotent (IF NOT EXISTS / DO NOTHING patterns).
--
-- No new RLS gates needed: altering an existing RLS-protected table.
-- The existing admin-read + service-role-all policies already cover
-- any new columns that land via ALTER TABLE.
--
-- Committed-not-applied: applied to production out-of-band by the operator
-- after this PR is merged (supabase db push or MCP apply_migration).

begin;

alter table public.feedback_status
  add column if not exists severity       text,
  add column if not exists area           text,
  add column if not exists reporter_id    text,
  add column if not exists dispatch_ref   text,
  add column if not exists dispatch_status text;

commit;

-- ── Rollback ───────────────────────────────────────────────────────────────
-- alter table public.feedback_status
--   drop column if exists severity,
--   drop column if exists area,
--   drop column if exists reporter_id,
--   drop column if exists dispatch_ref,
--   drop column if exists dispatch_status;
