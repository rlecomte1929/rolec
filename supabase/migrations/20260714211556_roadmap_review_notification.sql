-- [AIQ-1526] Record the outcome of the "your roadmap needs review" email to HR.
--
-- When a roadmap is generated it is held for HR approval (roadmap_review_status,
-- released_to_user = false) and the employee can read but not act on it. Nothing told HR
-- the plan was waiting — they had to open the case by chance while the employee sat
-- unable to start. We now email the case's HR owner the moment the plan is ready.
--
-- These columns record whether that email actually landed. Without them the feature is
-- unverifiable: "did HR get told?" has no answer, and a send that silently reaches nobody
-- is indistinguishable from success. In particular `unreachable` makes visible the cases
-- where NO HR contact resolves at all (measured at 10 of 47 cases with a roadmap today) —
-- an employee blocked with nobody to tell.
--
-- No new table, so no new RLS gate: public.roadmap_review_status already has RLS enabled
-- with its policies, and ADD COLUMN inherits them.

ALTER TABLE public.roadmap_review_status
  ADD COLUMN IF NOT EXISTS notified_at   timestamptz,
  ADD COLUMN IF NOT EXISTS notify_status text,
  ADD COLUMN IF NOT EXISTS notified_to   text;

COMMENT ON COLUMN public.roadmap_review_status.notified_at IS
  'When HR was successfully told the roadmap needs review. NULL = not (yet) delivered.';
COMMENT ON COLUMN public.roadmap_review_status.notify_status IS
  'sent | no_key | failed | error | unreachable. "unreachable" = no HR email could be resolved for the case.';
COMMENT ON COLUMN public.roadmap_review_status.notified_to IS
  'The address we actually reached, for audit/debug.';

-- Drives the ops metrics panel (pending queue, undelivered, unreachable).
CREATE INDEX IF NOT EXISTS roadmap_review_status_pending_notify_idx
  ON public.roadmap_review_status (released_to_user, notified_at);
