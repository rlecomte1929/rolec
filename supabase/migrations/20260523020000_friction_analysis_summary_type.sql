-- PRODUCT-6D: Add 'friction_analysis' to daily_summaries.summary_type CHECK constraint
-- and register the friction-analysis Edge Function as a daily pg_cron job at 04:00 UTC.

-- ─── 1. Widen the summary_type CHECK constraint ───────────────────────────────
-- The original CHECK was created inline in 20260524000001_analytics_events_and_daily_summaries.sql
-- PostgreSQL auto-names it daily_summaries_summary_type_check.
--
-- REPLAY-SAFE GUARD (2026-06-03):
-- public.daily_summaries is created by 20260524000001_analytics_events_and_daily_summaries.sql,
-- which sorts AFTER this file (20260523020000) in migration-replay order. On a fresh
-- `supabase db reset` the table therefore does not yet exist when this runs, and the bare
-- ALTER aborts the whole replay with ERROR 42P01 (relation "public.daily_summaries" does not
-- exist). Guarding on to_regclass lets a clean replay walk past this migration while still
-- applying the widened constraint anywhere the table already exists. Prod-verified 2026-06-03:
-- daily_summaries present with friction_analysis already in the CHECK (applied out-of-band),
-- and this migration name is absent from supabase_migrations.schema_migrations — so the guard
-- is a no-op on prod and an effect-preserving change. No migration inserts a friction_analysis
-- row, so the value being absent on a throwaway shadow DB causes no downstream replay failure.

do $$
begin
  if to_regclass('public.daily_summaries') is not null then
    alter table public.daily_summaries
      drop constraint if exists daily_summaries_summary_type_check;

    alter table public.daily_summaries
      add constraint daily_summaries_summary_type_check
      check (summary_type in (
        'user_behaviour',
        'assignments',
        'platform_health',
        'friction_analysis'
      ));
  end if;
end $$;

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
