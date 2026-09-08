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

-- Replay-safe guard — skips when pg_cron/pg_net unavailable (local/Preview replay).
-- On prod both exist, so the schedule runs unchanged. (Pattern: 20260523010000.)
DO $outer$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron')
  AND EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_net') THEN

    -- Remove existing job if present (idempotent)
    IF EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'pre-call-brief-poll') THEN
      PERFORM cron.unschedule('pre-call-brief-poll');
    END IF;

    -- Schedule every 15 minutes
    PERFORM cron.schedule(
      'pre-call-brief-poll',
      '*/15 * * * *',
      $cron$
        select net.http_post(
          url     := current_setting('app.supabase_url') || '/functions/v1/pre-call-brief',
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
    IF NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'pre-call-brief-poll') THEN
      RAISE EXCEPTION 'Failed to schedule pre-call-brief-poll cron job';
    END IF;
    RAISE NOTICE 'pre-call-brief-poll scheduled every 15 minutes ✓';
  ELSE
    RAISE NOTICE 'pg_cron or pg_net not available — skipping pre-call-brief cron schedule.';
  END IF;
END $outer$;
