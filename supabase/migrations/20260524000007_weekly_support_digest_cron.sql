-- SUPPORT-4E: Schedule weekly-support-digest Edge Function every Monday 08:00 UTC
-- ─────────────────────────────────────────────────────────────────────────────
-- Timeline (UTC):
--   01:00 Mon → autofix-pipeline runs
--   02:00 Mon → nightly-aggregation runs
--   07:00 Mon → morning-digest (daily)
--   08:00 Mon → weekly-support-digest (support health summary)
-- ─────────────────────────────────────────────────────────���───────────────────

do $$
begin
  if exists (select 1 from cron.job where jobname = 'weekly-support-digest') then
    perform cron.unschedule('weekly-support-digest');
  end if;
end $$;

-- Every Monday at 08:00 UTC (cron: minute hour day-of-month month day-of-week)
select cron.schedule(
  'weekly-support-digest',
  '0 8 * * 1',
  $$
    select net.http_post(
      url     := current_setting('app.supabase_url') || '/functions/v1/weekly-support-digest',
      headers := jsonb_build_object(
        'Content-Type',  'application/json',
        'Authorization', 'Bearer ' || current_setting('app.service_role_key')
      ),
      body    := '{}'::jsonb
    )
    as request_id;
  $$
);

do $$
begin
  if not exists (select 1 from cron.job where jobname = 'weekly-support-digest') then
    raise exception 'Failed to schedule weekly-support-digest cron job';
  end if;
  raise notice 'weekly-support-digest scheduled at 08:00 UTC every Monday ✓';
end $$;
