-- BRAIN-3E: brain_update_reviews table + pg_cron jobs for monthly Company Brain auto-update
-- ─────────────────────────────────────────────────────────────────────────────
-- Tracks brain update review pages created by the brain-update Edge Function.
-- Monthly pg_cron job triggers delta generation; daily job checks for approvals.
--
-- Required env vars in Supabase vault:
--   NOTION_TOKEN                — Notion integration secret
--   ANTHROPIC_API_KEY           — Claude API key
--   BRAIN_PAGE_ID               — BRAIN-3D page ID (optional; defaults to AIQ-324)
--   PAIN_POINTS_DB_ID           — Notion Pain Points database ID (optional)
--   OPPORTUNITIES_DB_ID         — Notion Product Opportunities database ID (optional)
--   FEATURES_DB_ID              — Notion Feature Requests database ID (optional)
--
-- Requires: pg_cron and pg_net extensions
-- ─────────────────────────────────────────────────────────────────────────────

-- ─── Table ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.brain_update_reviews (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at      timestamptz DEFAULT now() NOT NULL,
  month_label     text NOT NULL,              -- 'YYYY-MM' e.g. '2026-05'
  notion_page_id  text,                       -- Notion review page UUID
  notion_page_url text,                       -- Direct link for Romain
  insights_count  int DEFAULT 0,              -- number of new insights in this review
  status          text DEFAULT 'pending'
                  CHECK (status IN ('pending', 'applied', 'rejected')),
  applied_at      timestamptz                 -- set when status → 'applied'
);

-- Prevent duplicate reviews for the same month
CREATE UNIQUE INDEX IF NOT EXISTS brain_update_reviews_month_uniq
  ON public.brain_update_reviews (month_label);

COMMENT ON TABLE public.brain_update_reviews IS
  'Tracks monthly Company Brain (BRAIN-3D) update reviews created by the brain-update Edge Function.';

-- ─── Row-level security ───────────────────────────────────────────────────────

ALTER TABLE public.brain_update_reviews ENABLE ROW LEVEL SECURITY;

-- Service role (Edge Function) can do everything
CREATE POLICY "service_role_brain_update_reviews" ON public.brain_update_reviews
  FOR ALL USING (auth.role() = 'service_role');

-- Authenticated users can read (e.g., for admin dashboard queries)
CREATE POLICY "authenticated_read_brain_update_reviews" ON public.brain_update_reviews
  FOR SELECT USING (auth.role() = 'authenticated');

-- ─── pg_cron jobs ─────────────────────────────────────────────────────────────

-- Remove existing jobs if present (idempotent re-run)
select cron.unschedule('brain-update-monthly')
where exists (select 1 from cron.job where jobname = 'brain-update-monthly');

select cron.unschedule('brain-update-apply-approvals')
where exists (select 1 from cron.job where jobname = 'brain-update-apply-approvals');

-- Monthly: 1st of each month at 08:00 UTC — generate delta from recent insights
select cron.schedule(
  'brain-update-monthly',
  '0 8 1 * *',
  $$
    select net.http_post(
      url     := current_setting('app.supabase_url') || '/functions/v1/brain-update',
      headers := jsonb_build_object(
        'Content-Type',  'application/json',
        'Authorization', 'Bearer ' || current_setting('app.service_role_key')
      ),
      body    := '{}'::jsonb
    )
    as request_id;
  $$
);

-- Daily: every day at 09:00 UTC — check for approved review pages and apply deltas
select cron.schedule(
  'brain-update-apply-approvals',
  '0 9 * * *',
  $$
    select net.http_post(
      url     := current_setting('app.supabase_url') || '/functions/v1/brain-update',
      headers := jsonb_build_object(
        'Content-Type',  'application/json',
        'Authorization', 'Bearer ' || current_setting('app.service_role_key')
      ),
      body    := '{"check_approvals": true}'::jsonb
    )
    as request_id;
  $$
);

-- ─── Verify ───────────────────────────────────────────────────────────────────

do $$
begin
  if not exists (select 1 from cron.job where jobname = 'brain-update-monthly') then
    raise exception 'Failed to schedule brain-update-monthly cron job';
  end if;
  if not exists (select 1 from cron.job where jobname = 'brain-update-apply-approvals') then
    raise exception 'Failed to schedule brain-update-apply-approvals cron job';
  end if;
  raise notice 'brain-update-monthly scheduled on 1st of each month at 08:00 UTC ✓';
  raise notice 'brain-update-apply-approvals scheduled daily at 09:00 UTC ✓';
end $$;
