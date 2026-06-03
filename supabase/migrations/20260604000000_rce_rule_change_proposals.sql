-- C2-04 · Rule scraper RuleChangeProposal queue (AIQ-555)
--
-- Architecture Report §5.2 — closes the feedback loop between live regulation
-- (UDI, BAMF, dejure.org) and the rule engine. The daily scraper writes
-- DIFF-BASED proposal rows into this table; it NEVER promotes or applies a rule
-- change. Romain reviews every proposal before promotion (status transitions
-- 'pending' -> 'promoted' | 'rejected' happen via the C2-05 admin UI, not the
-- scraper). This table is therefore a HUMAN-REVIEW QUEUE by construction.
--
-- Adds one table to the rce.* ontology (introduced in C1-01,
-- 20260528020000_relopass_case_engine_v1.sql):
--
--   rce.rule_change_proposals  — one row per detected change to a tracked
--                                regulation source, awaiting human review.
--
-- Idempotency: UNIQUE (rule_id, captured_html_hash). The hash is computed over
-- a normalised text extract (whitespace-collapsed), not raw HTML, so cosmetic
-- page changes don't trigger false proposals, and re-running the scraper on
-- identical content is a no-op (ON CONFLICT DO NOTHING in the writer).
--
-- SEC-003 HARD GATE compliance (root + backend CLAUDE.md): this new table gets
--   1. ENABLE ROW LEVEL SECURITY
--   2. At least one tenant/role-scoped policy (admin-only + service_role)
--   3. REVOKE ALL FROM anon
-- This is an admin-only internal table — read/write is scoped to admins
-- (public.admin_allowlist) and service_role. anon and ordinary authenticated
-- users get nothing.

-- ─────────────────────────────────────────────────────────────────────────────
-- Table
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE rce.rule_change_proposals (
  proposal_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- The rule this proposal would affect, if matched. Nullable so a brand-new
  -- regulation page (no existing rule) can still raise a proposal for triage.
  rule_id            TEXT REFERENCES rce.rules(rule_id) ON DELETE SET NULL,
  -- The rule_version whose `body`/source the captured content was diffed
  -- against. Nullable for first-seen sources.
  current_version_id UUID REFERENCES rce.rule_versions(rule_version_id) ON DELETE SET NULL,
  -- Stable source identifier from the seeded source list (e.g. UDI_VIKTIGE_MELDINGER).
  source_id          TEXT NOT NULL,
  source_url         TEXT NOT NULL,
  captured_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- SHA-256 over the NORMALISED text extract (whitespace-collapsed), not raw HTML.
  captured_html_hash TEXT NOT NULL,
  -- The normalised text extract that produced the hash (for side-by-side review).
  captured_text      TEXT,
  -- LLM-generated (gpt-4o-mini, <=500 tokens) or deterministic diff summary.
  diff_summary       TEXT,
  -- Review state. The scraper ONLY ever writes 'pending'. Promotion/rejection is
  -- a human action via the C2-05 admin UI. No automatic promotion — ever.
  status             TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','promoted','rejected')),
  resolved_by_user_id UUID,
  resolved_at        TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Idempotency key: same rule + same normalised content => same proposal.
  UNIQUE (rule_id, captured_html_hash)
);

-- Review-queue read pattern: "show me all pending proposals, newest first".
CREATE INDEX rule_change_proposals_pending
  ON rce.rule_change_proposals (status, captured_at DESC);

CREATE INDEX rule_change_proposals_by_rule
  ON rce.rule_change_proposals (rule_id, captured_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- SEC-003 hard gate: RLS + admin/service-role policy + REVOKE FROM anon
-- Admin-only internal table. Drop-then-recreate (no IF NOT EXISTS on policy),
-- mirroring the public.agent_runs admin/service-role convention.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE rce.rule_change_proposals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rule_change_proposals_service_role_all ON rce.rule_change_proposals;
DROP POLICY IF EXISTS rule_change_proposals_admin_all ON rce.rule_change_proposals;

-- Service role full access: the scraper writes through the service key.
-- (service_role bypasses RLS regardless, but the explicit policy documents intent.)
CREATE POLICY rule_change_proposals_service_role_all
  ON rce.rule_change_proposals FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- Admins (public.admin_allowlist) may read and resolve proposals via the
-- C2-05 review UI. No ordinary-authenticated or anon access.
CREATE POLICY rule_change_proposals_admin_all
  ON rce.rule_change_proposals FOR ALL
  USING (auth.uid() IN (SELECT user_id FROM public.admin_allowlist))
  WITH CHECK (auth.uid() IN (SELECT user_id FROM public.admin_allowlist));

REVOKE ALL ON rce.rule_change_proposals FROM anon;
-- Defence-in-depth: ordinary authenticated users get nothing at the GRANT level
-- either; only admins (via the policy above) and service_role touch this table.
REVOKE ALL ON rce.rule_change_proposals FROM authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON rce.rule_change_proposals TO authenticated;
GRANT ALL ON rce.rule_change_proposals TO service_role;

COMMENT ON TABLE rce.rule_change_proposals IS
  'C2-04 (AIQ-555): human-review queue of diff-based regulation changes scraped '
  'daily from UDI/BAMF/dejure. The scraper writes proposals (status=pending) only '
  'and NEVER auto-promotes rule changes; promotion is a human action via C2-05.';

COMMENT ON COLUMN rce.rule_change_proposals.captured_html_hash IS
  'SHA-256 over the NORMALISED text extract (whitespace-collapsed), not raw HTML. '
  'Part of the UNIQUE (rule_id, captured_html_hash) idempotency key.';

COMMENT ON COLUMN rce.rule_change_proposals.status IS
  'Review state. The scraper only ever writes pending. promoted/rejected are set '
  'by a human reviewer via the C2-05 admin UI — there is no automatic promotion.';

-- ─────────────────────────────────────────────────────────────────────────────
-- Cron registration (existing supabase pg_cron pattern, see
-- 20260523010000_nightly_aggregation_cron.sql). Runs daily at 03:00 UTC and
-- posts to the rule-scraper Edge Function, which invokes the LangGraph job in
-- backend/relopass/jobs/rule_scraper.py. Skips silently where pg_cron / pg_net
-- are unavailable (local dev).
-- ─────────────────────────────────────────────────────────────────────────────

DO $outer$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron')
    AND EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_net') THEN

        -- Remove any existing schedule (idempotent re-run)
        PERFORM cron.unschedule('rce-rule-scraper-daily')
        FROM cron.job
        WHERE jobname = 'rce-rule-scraper-daily';

        PERFORM cron.schedule(
            'rce-rule-scraper-daily',
            '0 3 * * *',   -- Every day at 03:00 UTC
            $cron$
            SELECT net.http_post(
                url     := current_setting('app.supabase_edge_url', true)
                           || '/rce-rule-scraper',
                headers := jsonb_build_object(
                    'Content-Type',  'application/json',
                    'Authorization', 'Bearer '
                        || current_setting('app.supabase_service_key', true)
                ),
                body    := '{"trigger":"cron"}'::jsonb
            );
            $cron$
        );

        RAISE NOTICE 'pg_cron job "rce-rule-scraper-daily" registered (03:00 UTC).';
    ELSE
        RAISE NOTICE 'pg_cron or pg_net not available — skipping rce-rule-scraper cron schedule.';
    END IF;
END $outer$;
