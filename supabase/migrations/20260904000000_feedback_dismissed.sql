-- Soft-dismiss for the admin Pilot Feedback log: hide a row from the default view
-- without destroying it (works for every stream, incl. ML-feedback rows we never
-- hard-delete). Null = active; a timestamp = dismissed at that time. Additive;
-- blanket admin RLS covers it; the app reads feedback_status via the service-role backend.

ALTER TABLE public.feedback_status
  ADD COLUMN IF NOT EXISTS dismissed_at TIMESTAMPTZ;
