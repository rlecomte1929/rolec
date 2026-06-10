-- AIQ-804 / P1-05d-followup: seed a default source-freshness crawl schedule.
--
-- The scheduler infrastructure already ships (P3-02a): the GitHub Actions cron
-- `.github/workflows/crawl-scheduler.yml` runs daily at 03:00 UTC and calls
-- POST /api/crons/process-crawl-schedules -> process_due_schedules() ->
-- run_crawl_for_scope() for every due, active row in public.crawl_schedules.
--
-- But crawl_schedules was EMPTY, so the daily cron processed nothing and
-- source_pages.last_fetched_at stayed frozen at the backfill/deploy time —
-- which is exactly the "Last verified is stale" symptom AIQ-804 describes.
-- (Verified 2026-06-10: 0 schedule rows; most_recent source_pages.last_fetched_at
-- = 2026-06-04, the backfill.)
--
-- This seeds ONE weekly, all-source schedule so the existing cron actually
-- crawls and keeps the dossier "Last verified" date honest:
--   * schedule_type='interval', schedule_expression='168'  -> weekly (168h);
--     interval avoids any croniter dependency in _compute_next_run.
--   * source_scope_type='all' (no country/city/domain/ref) -> process_due_schedules
--     calls run_crawl_for_scope(None, None, None, None) -> crawls ALL sources.
--   * next_run_at = now() -> immediately due, so the next daily 03:00 cron run
--     executes it; thereafter update_schedule_after_run advances it by 168h.
--
-- NOTE: applying this row TURNS ON scheduled outbound crawling of the configured
-- (external, e.g. government) source URLs on the next cron tick. To pause it:
--   UPDATE public.crawl_schedules SET is_active = false WHERE name = '<name below>';
--
-- Idempotent: keyed on the schedule name; re-running is a no-op.

INSERT INTO public.crawl_schedules
  (name, is_active, schedule_type, schedule_expression, source_scope_type, priority, next_run_at)
SELECT
  'Default source-freshness crawl (all sources, weekly)',
  true, 'interval', '168', 'all', 0, now()
WHERE NOT EXISTS (
  SELECT 1 FROM public.crawl_schedules
  WHERE name = 'Default source-freshness crawl (all sources, weekly)'
);
