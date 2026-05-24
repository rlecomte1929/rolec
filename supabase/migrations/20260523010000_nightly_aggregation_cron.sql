-- FOUNDATION-1D: Schedule the nightly-aggregation Edge Function via pg_cron
-- Runs daily at 02:00 UTC. Aggregates yesterday's events into daily_summaries.
-- Requires pg_cron + pg_net extensions (available on Supabase Pro+).
-- Skips silently if extensions are unavailable (e.g. local dev).

DO $outer$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron')
    AND EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_net') THEN

        -- Remove any existing schedule (idempotent re-run)
        PERFORM cron.unschedule('nightly-aggregation-daily')
        FROM cron.job
        WHERE jobname = 'nightly-aggregation-daily';

        PERFORM cron.schedule(
            'nightly-aggregation-daily',
            '0 2 * * *',   -- Every day at 02:00 UTC
            $cron$
            SELECT net.http_post(
                url     := current_setting('app.supabase_edge_url', true)
                           || '/nightly-aggregation',
                headers := jsonb_build_object(
                    'Content-Type',  'application/json',
                    'Authorization', 'Bearer '
                        || current_setting('app.supabase_service_key', true)
                ),
                body    := '{"trigger":"cron"}'::jsonb
            );
            $cron$
        );

        RAISE NOTICE 'pg_cron job "nightly-aggregation-daily" registered (02:00 UTC).';
    ELSE
        RAISE NOTICE 'pg_cron or pg_net not available — skipping nightly-aggregation cron schedule.';
    END IF;
END $outer$;
