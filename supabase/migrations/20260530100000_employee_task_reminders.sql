-- Migration: employee_tasks reminder dedup columns (AIQ-76 / AIQ-34-D)
--
-- Adds per-window reminder stamps so the daily D-7 / D-3 / D-0 reminder cron
-- (POST /api/crons/task-reminders) can send each reminder exactly once per task.
-- This mirrors the existing case_forms.deadline_reminded_at idempotency pattern;
-- no new public-schema table is introduced.

ALTER TABLE public.employee_tasks
  ADD COLUMN IF NOT EXISTS reminded_d7_at timestamptz,
  ADD COLUMN IF NOT EXISTS reminded_d3_at timestamptz,
  ADD COLUMN IF NOT EXISTS reminded_d0_at timestamptz;

-- Partial index: the cron only ever scans tasks with a due_date set.
CREATE INDEX IF NOT EXISTS idx_employee_tasks_due_date
  ON public.employee_tasks(due_date)
  WHERE due_date IS NOT NULL;
