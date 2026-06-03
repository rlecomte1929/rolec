-- P2 RLS hardening (defense-in-depth): explicit policies for backend-only tables.
--
-- Context: 37 tables in the public schema are RLS-enabled but carry ZERO
-- policies. With RLS on + no policy, every role except a BYPASSRLS role (i.e.
-- service_role / postgres) is implicitly denied — so these are already locked
-- to anon/authenticated. Audit confirmed (2026-06-05):
--   * 0 anon grants and 0 authenticated grants on all 37 tables, AND
--   * 0 frontend supabase-js `.from('<table>')` references to any of them.
-- The backend reaches every one of these through the service-role key, which
-- BYPASSES RLS, so it is unaffected either way (all 37 retain service_role
-- grants).
--
-- Why touch them at all: "RLS enabled, no policy" trips the Supabase security
-- advisor (rls_enabled_no_policy) and leaves the intended access model implicit.
-- This migration makes the posture explicit and silences the lint by adding a
-- single service-role ALL policy per table plus an idempotent REVOKE of anon.
--
-- Deliberately NOT adding `authenticated` policies: none of these tables have a
-- live supabase-js read path (verified above), so a tenant-scoped authenticated
-- policy would be dead code. If a future frontend path needs direct supabase-js
-- access to one of these, add an explicit tenant-scoped policy + GRANT then.
--
-- Replay-safe: DROP POLICY IF EXISTS before each CREATE, and REVOKE is a no-op
-- when the grant was never present. Safe to run on a fresh `supabase db reset`
-- and safe to replay against prod.

DO $$
DECLARE
  t text;
  tables text[] := ARRAY[
    'admin_allowlist',
    'admin_sessions',
    'analytics_events',
    'audit_log',
    'audit_logs',
    'canonical_policy_query_audit_logs',
    'catalog_employee_demand',
    'catalog_scrape_quota',
    'collaboration_comment_mentions',
    'collaboration_comments',
    'collaboration_notifications',
    'collaboration_thread_participants',
    'collaboration_threads',
    'compliance_reference_sources',
    'crawl_job_runs',
    'crawl_runs',
    'crawl_schedules',
    'crawled_source_chunks',
    'crawled_source_documents',
    'demo_request_rate_limits',
    'demo_requests',
    'document_change_events',
    'freshness_alerts',
    'freshness_snapshots',
    'knowledge_doc_ingest_jobs',
    'notification_outbox',
    'ops_notification_events',
    'prospect_candidates',
    'research_source_candidates',
    'review_queue_activity_log',
    'review_queue_items',
    'sessions',
    'source_records',
    'staged_event_candidates',
    'staged_resource_candidates',
    'staging_review_audit_log',
    'support_case_notes'
  ];
BEGIN
  FOREACH t IN ARRAY tables LOOP
    -- Skip cleanly if the table is absent in a given environment.
    IF to_regclass('public.' || t) IS NULL THEN
      RAISE NOTICE 'skipping missing table public.%', t;
      CONTINUE;
    END IF;

    -- RLS must be on for the policy to take effect (no-op if already enabled).
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', t);

    -- Explicit service-role ALL policy. service_role bypasses RLS, so this
    -- grants no new access; it documents intent and clears the advisor lint.
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I;', t || '_service_role_all', t);
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true);',
      t || '_service_role_all', t
    );

    -- Defense-in-depth: ensure anon has no Data API grant (idempotent no-op
    -- when none was present, which is the case for all 37 today).
    EXECUTE format('REVOKE ALL ON public.%I FROM anon;', t);
  END LOOP;
END$$;
