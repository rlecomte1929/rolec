-- Reserved columns on public.feedback for a per-row Notion Work Queue link. The live
-- fix-trigger flow tracks dispatch state on feedback_status (dispatch_ref/dispatch_status),
-- so these columns are currently unused by the console — kept for a possible future
-- product-stream link-back and applied out-of-band on request.
--   notion_task_id / notion_task_url / notion_status / aiq_id
--
-- ALTER on an existing table (no new table → the new-table RLS hard-gate does not apply).
-- All nullable, idempotent. Applied to prod 2026-07-06 via execute_sql; ledger reconciled.

alter table public.feedback
  add column if not exists notion_task_id  text,
  add column if not exists notion_task_url text,
  add column if not exists notion_status   text,
  add column if not exists aiq_id          text;
