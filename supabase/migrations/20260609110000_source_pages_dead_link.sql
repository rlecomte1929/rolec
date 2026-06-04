-- P3-02d · Dead-link detection: consecutive 404 counter on source_pages
--
-- Adds a consecutive_404_count column so the dead-link detection service
-- can track how many times in a row a URL returned HTTP 404. When the count
-- reaches 3 the URL is treated as a dead link and an ops_notification fires.
--
-- The column is reset to 0 on every successful fetch, incrementd on every
-- 404, and never touched by other status codes (502/503 are transient failures
-- handled by the retry logic in P3-02a, not dead-link logic).
--
-- Idempotent: the IF NOT EXISTS guard makes re-runs safe.

alter table public.source_pages
  add column if not exists consecutive_404_count integer not null default 0;

comment on column public.source_pages.consecutive_404_count is
  'Number of consecutive HTTP 404 responses for this URL. Reset to 0 on any successful fetch. When >= 3 the URL is flagged as a dead link and an ops_notification is created (P3-02d).';
