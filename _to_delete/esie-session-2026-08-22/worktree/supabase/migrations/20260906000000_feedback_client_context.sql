-- Add feedback.client_context: a diagnostics snapshot captured by the FeedbackWidget at
-- submit time (page/route, the failing function from the error-tracking fingerprint,
-- recent failed API requests + X-Request-ID correlation id, breadcrumb trail, viewport,
-- app build SHA). Rendered in the admin "Feedback & Work" Diagnostics panel so a triager
-- can see where/what failed and pivot to the backend request log by request-id.
--
-- ALTER on an existing table (no new table → the new-table RLS hard-gate does not apply).
-- Nullable; older clients / non-product streams simply leave it NULL. Idempotent.

alter table public.feedback
  add column if not exists client_context jsonb;
