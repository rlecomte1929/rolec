-- Reporter identity snapshot for product feedback submissions.
--
-- The admin Pilot Feedback log could only show a raw user_id UUID (often NULL for
-- legacy/HR sessions where auth.uid() was null). We now snapshot the reporter's
-- name / email / role at submit time from the authenticated ReloPass session, so
-- the admin can always see WHO reported an issue or idea — even when user_id is NULL.
--
-- No RLS change needed: the blanket admin SELECT/UPDATE policies on public.feedback
-- already cover new columns, and the app reads this table via the service-role
-- backend connection (bypassing RLS) anyway.

ALTER TABLE public.feedback
  ADD COLUMN IF NOT EXISTS reporter_email TEXT,
  ADD COLUMN IF NOT EXISTS reporter_name  TEXT,
  ADD COLUMN IF NOT EXISTS reporter_role  TEXT;
