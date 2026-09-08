-- DEV-LOOP-2C: Schedule autofix-pipeline Edge Function at 01:00 UTC daily
-- ─────────────────────────────────────────────────────────────────────────────
-- The nightly-aggregation runs at 02:00 UTC; the autofix pipeline runs at 01:00
-- so that the most recent daily digest is available before fixes are proposed.
--
-- Requires: pg_cron and pg_net extensions (enabled via FOUNDATION-1A)
-- ─────────────────────────────────────────────────────────────────────────────

-- Skips silently if pg_cron / pg_net are unavailable (e.g. local dev / Preview
-- replay). On prod both extensions exist, so the THEN branch runs the original
-- schedule unchanged. (Replay-safe guard — same pattern as 20260523010000.)
DO $outer$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron')
  AND EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_net') THEN

    -- Remove existing job if present (idempotent)
    PERFORM cron.unschedule('autofix-pipeline-daily')
    FROM cron.job
    WHERE jobname = 'autofix-pipeline-daily';

    -- Schedule at 01:00 UTC daily
    PERFORM cron.schedule(
      'autofix-pipeline-daily',
      '0 1 * * *',
      $cron$
        select net.http_post(
          url     := current_setting('app.supabase_url') || '/functions/v1/autofix-pipeline',
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
    IF NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'autofix-pipeline-daily') THEN
      RAISE EXCEPTION 'Failed to schedule autofix-pipeline-daily cron job';
    END IF;
    RAISE NOTICE 'autofix-pipeline-daily scheduled at 01:00 UTC ✓';
  ELSE
    RAISE NOTICE 'pg_cron or pg_net not available — skipping autofix-pipeline cron schedule.';
  END IF;
END $outer$;
