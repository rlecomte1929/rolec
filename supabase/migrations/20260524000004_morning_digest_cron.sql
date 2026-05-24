-- DEV-LOOP-2E: Schedule morning-digest Edge Function at 07:00 UTC daily
-- ─────────────────────────────────────────────────────────────────────────────
-- Timeline:
--   01:00 UTC → autofix-pipeline runs (fixes bugs, creates PRs)
--   02:00 UTC → nightly-aggregation runs (generates daily_summaries)
--   07:00 UTC → morning-digest runs (Romain sees what happened overnight)
-- ─────────────────────────────────────────────────────────────────────────────

-- Remove existing job if present (idempotent)
do $$
begin
  if exists (select 1 from cron.job where jobname = 'morning-digest-daily') then
    perform cron.unschedule('morning-digest-daily');
  end if;
end $$;

-- Schedule at 07:00 UTC daily
select cron.schedule(
  'morning-digest-daily',
  '0 7 * * *',
  $$
    select net.http_post(
      url     := current_setting('app.supabase_url') || '/functions/v1/morning-digest',
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
  if not exists (select 1 from cron.job where jobname = 'morning-digest-daily') then
    raise exception 'Failed to schedule morning-digest-daily cron job';
  end if;
  raise notice 'morning-digest-daily scheduled at 07:00 UTC ✓';
end $$;
