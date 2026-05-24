-- PRODUCT-6D: Add 'friction_analysis' to daily_summaries.summary_type CHECK constraint
-- and register the friction-analysis Edge Function as a daily pg_cron job at 04:00 UTC.

-- ─── 1. Widen the summary_type CHECK constraint ───────────────────────────────
-- The original CHECK was created inline in 20260524000001_analytics_events_and_daily_summaries.sql
-- PostgreSQL auto-names it daily_summaries_summary_type_check.

ALTER TABLE public.daily_summaries
  DROP CONSTRAINT IF EXISTS daily_summaries_summary_type_check;

ALTER TABLE public.daily_summaries
  ADD CONSTRAINT daily_summaries_summary_type_check
  CHECK (summary_type IN (
    'user_behaviour',
    'assignments',
    'platform_health',
    'friction_analysis'
  ));

-- ─── 2. Register pg_cron job at 04:00 UTC ────────────────────────────────────

DO $outer$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron')
    AND EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_net') THEN

        -- Remove any existing schedule (idempotent re-run)
        PERFORM cron.unschedule('friction-analysis-daily')
        FROM cron.job
        WHERE jobname = 'friction-analysis-daily';

        PERFORM cron.schedule(
            'friction-analysis-daily',
            '0 4 * * *',   -- Every day at 04:00 UTC (after nightly-aggregation at 02:00)
            $cron$
            SELECT net.http_post(
                url     := current_setting('app.supabase_edge_url', true)
                           || '/friction-analysis',
                headers := jsonb_build_object(
                    'Content-Type',  'application/json',
                    'Authorization', 'Bearer '
                        || current_setting('app.supabase_service_key', true)
                ),
                body    := '{"trigger":"cron"}'::jsonb
            );
            $cron$
        );

        RAISE NOTICE 'pg_cron job "friction-analysis-daily" registered (04:00 UTC).';
    ELSE
        RAISE NOTICE 'pg_cron or pg_net not available — skipping friction-analysis cron schedule.';
    END IF;
END $outer$;
