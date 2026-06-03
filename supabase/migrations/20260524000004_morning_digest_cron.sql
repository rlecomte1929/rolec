-- DEV-LOOP-2E: Schedule morning-digest Edge Function at 07:00 UTC daily
-- ─────────────────────────────────────────────────────────────────────────────
-- Timeline:
--   01:00 UTC → autofix-pipeline runs (fixes bugs, creates PRs)
--   02:00 UTC → nightly-aggregation runs (generates daily_summaries)
--   07:00 UTC → morning-digest runs (Romain sees what happened overnight)
-- ─────────────────────────────────────────────────────────────────────────────

-- Replay-safe guard — skips when pg_cron/pg_net unavailable (local/Preview replay).
-- On prod both exist, so the schedule runs unchanged. (Pattern: 20260523010000.)
DO $outer$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron')
  AND EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_net') THEN

    -- Remove existing job if present (idempotent)
    IF EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'morning-digest-daily') THEN
      PERFORM cron.unschedule('morning-digest-daily');
    END IF;

    -- Schedule at 07:00 UTC daily
    PERFORM cron.schedule(
      'morning-digest-daily',
      '0 7 * * *',
      $cron$
        select net.http_post(
          url     := current_setting('app.supabase_url') || '/functions/v1/morning-digest',
          headers := jsonb_build_object(
            'Content-Type',  'application/json',
            'Authorization', 'Bearer ' || current_setting('app.service_role_key')
          ),
          body    := '{}'::jsonb
        )
        as request_id;
      $cron$
    );

    -- Verify job was created
    IF NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'morning-digest-daily') THEN
      RAISE EXCEPTION 'Failed to schedule morning-digest-daily cron job';
    END IF;
    RAISE NOTICE 'morning-digest-daily scheduled at 07:00 UTC ✓';
  ELSE
    RAISE NOTICE 'pg_cron or pg_net not available — skipping morning-digest cron schedule.';
  END IF;
END $outer$;
