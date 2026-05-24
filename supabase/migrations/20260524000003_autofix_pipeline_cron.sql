-- DEV-LOOP-2C: Schedule autofix-pipeline Edge Function at 01:00 UTC daily
-- ─────────────────────────────────────────────────────────────────────────────
-- The nightly-aggregation runs at 02:00 UTC; the autofix pipeline runs at 01:00
-- so that the most recent daily digest is available before fixes are proposed.
--
-- Requires: pg_cron and pg_net extensions (enabled via FOUNDATION-1A)
-- ─────────────────────────────────────────────────────────────────────────────

-- Remove existing job if present (idempotent)
select cron.unschedule('autofix-pipeline-daily')
where exists (
  select 1 from cron.job where jobname = 'autofix-pipeline-daily'
);

-- Schedule at 01:00 UTC daily
select cron.schedule(
  'autofix-pipeline-daily',
  '0 1 * * *',
  $$
    select net.http_post(
      url     := current_setting('app.supabase_url') || '/functions/v1/autofix-pipeline',
      headers := jsonb_build_object(
        'Content-Type',  'application/json',
        'Authorization', 'Bearer ' || current_setting('app.service_role_key')
      ),
      body    := '{}'::jsonb
    )
    as request_id;
  $$
);

-- Verify job was created
do $$
begin
  if not exists (select 1 from cron.job where jobname = 'autofix-pipeline-daily') then
    raise exception 'Failed to schedule autofix-pipeline-daily cron job';
  end if;
  raise notice 'autofix-pipeline-daily scheduled at 01:00 UTC ✓';
end $$;
