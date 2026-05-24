-- HUMAN-7B: Schedule pre-call-brief Edge Function every 15 minutes via pg_cron
-- ─────────────────────────────────────────────────────────────────────────────
-- Scans Google Calendar every 15 minutes for meetings tagged 'ReloPass' or
-- 'HR call' starting in the next 30 minutes. For each match, generates an AI
-- pre-call brief with Claude Haiku and creates a Notion page.
--
-- Required env vars in Supabase vault:
--   GOOGLE_CALENDAR_TOKEN    — OAuth 2.0 bearer token (Google Calendar API)
--   ANTHROPIC_API_KEY        — Claude API key
--   NOTION_TOKEN             — Notion integration secret
--   NOTION_BRAIN_PAGE        — (optional) BRAIN-3D page ID
--   NOTION_BRIEFS_PARENT_ID  — (optional) parent page ID for brief pages
--
-- Requires: pg_cron and pg_net extensions
-- ─────────────────────────────────────────────────────────────────────────────

-- Remove existing job if present (idempotent)
select cron.unschedule('pre-call-brief-poll')
where exists (
  select 1 from cron.job where jobname = 'pre-call-brief-poll'
);

-- Schedule every 15 minutes
select cron.schedule(
  'pre-call-brief-poll',
  '*/15 * * * *',
  $$
    select net.http_post(
      url     := current_setting('app.supabase_url') || '/functions/v1/pre-call-brief',
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
  if not exists (select 1 from cron.job where jobname = 'pre-call-brief-poll') then
    raise exception 'Failed to schedule pre-call-brief-poll cron job';
  end if;
  raise notice 'pre-call-brief-poll scheduled every 15 minutes ✓';
end $$;
