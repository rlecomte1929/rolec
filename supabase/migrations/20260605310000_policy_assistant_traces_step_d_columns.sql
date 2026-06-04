-- Add Parker Step D prompt-attribution columns to policy_assistant_traces.
--
-- The merged writer (db.insert_policy_assistant_trace / TraceSession.flush) already
-- INSERTs prompt_version_id and canary_arm, but the prod table was created by
-- 20260605000000_ai_unit_economics_reauthor.sql with only the 8 base + 6 Step G
-- columns. init_db() returns early on Postgres, so the SQLite-only ADD COLUMN
-- backfill never runs on prod. Without these columns every insert raises
-- UndefinedColumn, is swallowed by the best-effort try/except, and writes zero rows.
--
-- Additive + idempotent. No new table, so the new-table RLS hard-gates do not apply;
-- RLS is already enabled on policy_assistant_traces by the reauthor migration.

ALTER TABLE public.policy_assistant_traces ADD COLUMN IF NOT EXISTS prompt_version_id TEXT;
ALTER TABLE public.policy_assistant_traces ADD COLUMN IF NOT EXISTS canary_arm TEXT;
