-- SUPPORT-4E: Schedule weekly-support-digest Edge Function every Monday 08:00 UTC
-- ─────────────────────────────────────────────────────────────────────────────
-- Timeline (UTC):
--   01:00 Mon → autofix-pipeline runs
--   02:00 Mon → nightly-aggregation runs
--   07:00 Mon → morning-digest (daily)
--   08:00 Mon → weekly-support-digest (support health summary)
-- ─────────────────────────────────────────────────────────���───────────────────

-- Replay-safe guard — skips when pg_cron/pg_net unavailable (local/Preview replay).
-- On prod both exist, so the schedule runs unchanged. (Pattern: 20260523010000.)
DO $outer$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron')
  AND EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_net') THEN

    IF EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'weekly-support-digest') THEN
      PERFORM cron.unschedule('weekly-support-digest');
    END IF;

    -- Every Monday at 08:00 UTC (cron: minute hour day-of-month month day-of-week)
    PERFORM cron.schedule(
      'weekly-support-digest',
      '0 8 * * 1',
      $cron$
        select net.http_post(
          url     := current_setting('app.supabase_url') || '/functions/v1/weekly-support-digest',
          headers := jsonb_build_object(
            'Content-Type',  'application/json',
            'Authorization', 'Bearer ' || current_setting('app.service_role_key')
          ),
          body    := '{}'::jsonb
        )
        as request_id;
      $cron$
    );

    IF NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'weekly-support-digest') THEN
      RAISE EXCEPTION 'Failed to schedule weekly-support-digest cron job';
    END IF;
    RAISE NOTICE 'weekly-support-digest scheduled at 08:00 UTC every Monday ✓';
  ELSE
    RAISE NOTICE 'pg_cron or pg_net not available — skipping weekly-support-digest cron schedule.';
  END IF;
END $outer$;
