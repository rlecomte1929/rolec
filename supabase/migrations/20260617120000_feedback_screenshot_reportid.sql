-- Add screenshot capture and human-readable report ID to feedback submissions.
-- screenshot_data: JPEG base64 data URL captured from the page at submit time.
-- report_id: human-readable reference e.g. BUG-260617-A1B2 (generated client-side).

ALTER TABLE public.feedback
  ADD COLUMN IF NOT EXISTS screenshot_data TEXT,
  ADD COLUMN IF NOT EXISTS report_id       TEXT;

-- Index for fast admin lookup by report_id
CREATE INDEX IF NOT EXISTS feedback_report_id_idx ON public.feedback(report_id);

-- Allow authenticated users to submit with the new columns.
-- Existing INSERT policy ("authenticated users can submit feedback") already
-- covers all columns via WITH CHECK (auth.uid() = user_id) — no policy change needed.
