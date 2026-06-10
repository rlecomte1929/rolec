-- ============================================================================
-- P2-02d (AIQ-692) · Admin material-change review queue
--
-- When the source-change monitor classifies a crawled page diff as *material*
-- (source_change_classifier, P2-02b), it must NOT notify users automatically —
-- a human approves first. This migration adds the two tables that back that
-- human-in-the-loop gate:
--
--   public.source_change_reviews          — one row per pending material change
--                                           (rule_version + diff excerpt). An
--                                           admin approves (→ notify affected
--                                           active cases) or rejects (→ logged,
--                                           no notification).
--   public.case_rule_update_notifications — one row per affected case when a
--                                           review is approved. This is the
--                                           contract the in-app roadmap banner
--                                           (P2-02e) reads; dismissible per case.
--
-- Both tables are admin/backend-only: the FastAPI backend reaches them through
-- the service-role connection. Per the SEC-002/SEC-003 hard gate (root + backend
-- CLAUDE.md) every new public table gets: (1) RLS enabled, (2) >=1 policy,
-- (3) REVOKE FROM anon. No anon/authenticated Data-API access is intended.
--
-- Replay-safe: CREATE TABLE IF NOT EXISTS, DROP POLICY IF EXISTS before CREATE,
-- idempotent trigger drop/create, REVOKE is a no-op when no grant exists.
-- ============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- source_change_reviews
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.source_change_reviews (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- The rce rule_version whose source page changed. Not a cross-schema FK
  -- (rce.* lives in its own schema); integrity is enforced by the writer.
  rule_version_id    uuid NOT NULL,
  source_url         text,
  source_name        text,
  -- Human-readable old/new excerpts for the admin diff view.
  old_excerpt        text,
  new_excerpt        text,
  -- Structured classifier output (source_change_classifier.DiffClassification).
  changed_sections   jsonb NOT NULL DEFAULT '[]'::jsonb,
  status             text NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending', 'approved', 'rejected')),
  -- Snapshot of the active case_ids notified at approval time (audit trail).
  notified_case_ids  jsonb NOT NULL DEFAULT '[]'::jsonb,
  reviewed_by        text,
  reviewed_at        timestamptz,
  review_note        text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);

-- Queue read pattern: pending items, oldest first.
CREATE INDEX IF NOT EXISTS source_change_reviews_status_created
  ON public.source_change_reviews (status, created_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- case_rule_update_notifications
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.case_rule_update_notifications (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- The affected case (rce case_id). Text (not a cross-schema FK) so this table
  -- does not couple to the rce schema's lifecycle.
  case_id                  text NOT NULL,
  source_change_review_id  uuid NOT NULL
                             REFERENCES public.source_change_reviews(id) ON DELETE CASCADE,
  status                   text NOT NULL DEFAULT 'active'
                             CHECK (status IN ('active', 'dismissed')),
  created_at               timestamptz NOT NULL DEFAULT now(),
  dismissed_at             timestamptz,
  -- One live notification per (case, review): re-approving is idempotent.
  UNIQUE (case_id, source_change_review_id)
);

-- Banner read pattern: active notifications for a case.
CREATE INDEX IF NOT EXISTS case_rule_update_notifications_case_status
  ON public.case_rule_update_notifications (case_id, status);

-- ─────────────────────────────────────────────────────────────────────────────
-- updated_at trigger (source_change_reviews) — reuse public.set_updated_at
-- ─────────────────────────────────────────────────────────────────────────────
DROP TRIGGER IF EXISTS set_updated_at_source_change_reviews ON public.source_change_reviews;
CREATE TRIGGER set_updated_at_source_change_reviews
  BEFORE UPDATE ON public.source_change_reviews
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ─────────────────────────────────────────────────────────────────────────────
-- SEC hard gate: RLS + service-role policy + REVOKE anon, on both tables.
-- Backend reaches these through the service-role connection (which bypasses RLS
-- regardless); the explicit policy documents intent and closes the gate.
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.source_change_reviews ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS source_change_reviews_service_role_all ON public.source_change_reviews;
CREATE POLICY source_change_reviews_service_role_all
  ON public.source_change_reviews FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');
REVOKE ALL ON public.source_change_reviews FROM anon;
REVOKE ALL ON public.source_change_reviews FROM authenticated;
GRANT ALL ON public.source_change_reviews TO service_role;

ALTER TABLE public.case_rule_update_notifications ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS case_rule_update_notifications_service_role_all ON public.case_rule_update_notifications;
CREATE POLICY case_rule_update_notifications_service_role_all
  ON public.case_rule_update_notifications FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');
REVOKE ALL ON public.case_rule_update_notifications FROM anon;
REVOKE ALL ON public.case_rule_update_notifications FROM authenticated;
GRANT ALL ON public.case_rule_update_notifications TO service_role;

COMMENT ON TABLE public.source_change_reviews IS
  'P2-02d (AIQ-692): admin review queue of material source-page changes. Admin '
  'approves (notify affected active cases) or rejects (log, no notification) '
  'before any user is notified.';
COMMENT ON TABLE public.case_rule_update_notifications IS
  'P2-02d/e: per-case "rule updated — please review" notification, written on '
  'review approval and read by the in-app roadmap banner. Dismissible per case.';
