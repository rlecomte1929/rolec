-- Per-item context the admin adds before dispatching a feedback ticket to the
-- AI Work Queue. The Dispatch flow feeds this (plus the bug + classification)
-- to the task-engineer LLM. Additive; blanket admin RLS covers it; the app
-- reads feedback_status via the service-role backend.

ALTER TABLE public.feedback_status
  ADD COLUMN IF NOT EXISTS dispatch_context TEXT;
