-- Migration: messages_legacy_columns_compat
--
-- Fixes AIQ-461 (employee Inbox 500s). The platform-redesign migration
-- (20260520000000_platform_redesign_schema.sql) recreated public.messages with a
-- thread-based schema (thread_id, sender_id, sent_at, ...), which dropped the
-- assignment-based columns the legacy messaging code in backend/database.py still
-- queries. As a result both GET /api/employee/messages and
-- GET /api/messages/unread-count crash with "column does not exist".
--
-- The employee Inbox and HR conversation summaries have not yet been migrated to the
-- thread model, so they remain the live messaging surface. This restores the columns
-- they depend on (mirroring 20260322100000_hr_messages_schema_compat.sql, which the
-- redesign superseded). All columns are nullable / additive, so existing thread-based
-- rows are untouched and legacy reads return empty for fresh accounts.
--
-- No new table is created, so the RLS hard-gate does not apply; public.messages
-- already has RLS enabled by the redesign migration.

ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS assignment_id       text;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS hr_user_id          text;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS employee_identifier text;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS subject             text;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS status              text;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS delivered_at        timestamptz;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS read_at             timestamptz;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS dismissed_at        timestamptz;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS recipient_user_id   text;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS sender_user_id      text;

-- Index for the employee thread fan-out (WHERE assignment_id IN (...)).
CREATE INDEX IF NOT EXISTS idx_messages_assignment_id
  ON public.messages (assignment_id);

-- Index for unread-count / unread-list (recipient + read/dismissed filters).
CREATE INDEX IF NOT EXISTS idx_messages_recipient_unread_pg
  ON public.messages (recipient_user_id, read_at, dismissed_at, created_at DESC);
