-- P1-02a (AIQ-631): append-only specialist review calibration data + roadmap release flags.
-- Also consumed by P1-04 (calibration). Do not duplicate the events table elsewhere.

-- ── Enums ────────────────────────────────────────────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'specialist_review_action') THEN
    CREATE TYPE public.specialist_review_action AS ENUM ('approve', 'reject', 'edit');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'specialist_reason_code') THEN
    CREATE TYPE public.specialist_reason_code AS ENUM (
      'WRONG_PATHWAY', 'OUTDATED_RULE', 'MISSING_DEPENDENCY', 'INCORRECT_FORM'
    );
  END IF;
END$$;

-- ── Append-only events table ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.specialist_review_events (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id            TEXT NOT NULL,
  step_id            TEXT NOT NULL,
  reviewer_id        TEXT NOT NULL,
  action             public.specialist_review_action NOT NULL,
  reason_code        public.specialist_reason_code,
  original_step_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  edited_step_json   JSONB,
  reviewed_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sre_case_id ON public.specialist_review_events (case_id);
CREATE INDEX IF NOT EXISTS idx_sre_step_id ON public.specialist_review_events (step_id);

-- ── Per-case release / regeneration status (supports AIQ-634) ─────────────────
CREATE TABLE IF NOT EXISTS public.roadmap_review_status (
  case_id                TEXT PRIMARY KEY,
  released_to_user       BOOLEAN NOT NULL DEFAULT false,
  regeneration_requested BOOLEAN NOT NULL DEFAULT false,
  reviewer_id            TEXT,
  notes                  TEXT,
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── SEC-003 hard gate: RLS + policy + revoke + grant ─────────────────────────
ALTER TABLE public.specialist_review_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.roadmap_review_status    ENABLE ROW LEVEL SECURITY;

-- Append-only: admin SELECT + INSERT only. No UPDATE/DELETE policy => denied by RLS.
CREATE POLICY specialist_review_events_admin_select
  ON public.specialist_review_events FOR SELECT TO authenticated
  USING (public.is_admin());
CREATE POLICY specialist_review_events_admin_insert
  ON public.specialist_review_events FOR INSERT TO authenticated
  WITH CHECK (public.is_admin());

-- Status row is mutable by admin (upserted on each submit).
CREATE POLICY roadmap_review_status_admin_all
  ON public.roadmap_review_status FOR ALL TO authenticated
  USING (public.is_admin()) WITH CHECK (public.is_admin());

REVOKE ALL ON public.specialist_review_events FROM anon;
REVOKE ALL ON public.roadmap_review_status    FROM anon;

-- Append-only at grant level too: no UPDATE/DELETE on events.
GRANT SELECT, INSERT                 ON public.specialist_review_events TO authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.roadmap_review_status    TO authenticated, service_role;
