-- ============================================================
-- [P4-4] Notification system — deadline_reminded_at
-- ============================================================
-- Adds deadline_reminded_at to case_forms so the daily cron
-- can de-duplicate 7-day deadline reminder notifications.
-- The cron sets this column to now() after sending; it will
-- never fire again for that form.
-- ============================================================

ALTER TABLE public.case_forms
  ADD COLUMN IF NOT EXISTS deadline_reminded_at timestamptz;

COMMENT ON COLUMN public.case_forms.deadline_reminded_at IS
  '[P4-4] Timestamp when the 7-day deadline reminder was sent. NULL = not yet sent. Used by the daily cron to prevent duplicate reminders.';

-- Index to make the cron query fast: find all forms due in 7 days that
-- haven't been reminded yet.
CREATE INDEX IF NOT EXISTS idx_case_forms_deadline_reminder
  ON public.case_forms (deadline)
  WHERE deadline IS NOT NULL AND deadline_reminded_at IS NULL;
