-- ============================================================
-- [P5-5] User feedback collection + HR review queue
-- Date: 2026-05-22
--
-- Two tables, one hard contract: feedback is captured as a SIGNAL — it
-- never directly modifies policy_chunks or policy_values. Negative
-- feedback creates HR review queue items; HR is always the validation
-- gate.
--
-- Tables:
--   1. policy_feedback        — raw per-event rows (1 row per click)
--   2. policy_review_queue    — aggregated review items (1 row per (chunk
--                               set, question hash, company), increments
--                               feedback_count on dedup)
--
-- Privacy invariants:
--   - We do not store the original question text. policy_feedback.question_hash
--     is SHA-256 of the lowercased, whitespace-stripped question — the
--     application layer hashes before insert. The review_queue carries a
--     short response_summary (HR-visible) but no raw user PII.
--   - We do not store the employee's user_id on policy_feedback (only the
--     opaque session_id), matching the spec's "session_id not employee_id"
--     guidance.
--
-- Deduplication rule (handled at the application layer, not the DB):
--   - Same (company_id, question_hash, chunk_ids[]) → increment
--     feedback_count on the existing review_queue row, do NOT insert a new
--     one. If feedback_count >= 3 → priority='high'.
-- ============================================================

BEGIN;

-- ---------------------------------------------------------------
-- 1. policy_feedback — raw events (positive AND negative)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.policy_feedback (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  -- Opaque session identifier from the assistant UI; intentionally NOT
  -- linked to profiles.id so a positive thumbs-up can't be traced to an
  -- employee from this table alone.
  session_id      text NOT NULL,
  -- SHA-256 of the user's question, lowercased + whitespace-stripped.
  -- Allows dedup without storing the raw text.
  question_hash   text NOT NULL,
  -- Chunk IDs the assistant cited when answering this question, in the
  -- order they were shown. UUID[] preserves order; sorted before hashing
  -- for dedup grouping.
  chunk_ids       uuid[] NOT NULL DEFAULT '{}',
  rating          text NOT NULL CHECK (rating IN ('positive', 'negative')),
  comment         text,           -- optional HR-visible note from the employee
  created_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.policy_feedback IS
  '[P5-5] Per-event thumbs-up/down records for the AI assistant. Privacy-by-default: session_id only, no user_id, no raw question.';

CREATE INDEX IF NOT EXISTS idx_policy_feedback_company_created
  ON public.policy_feedback (company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_policy_feedback_question_hash
  ON public.policy_feedback (company_id, question_hash);

-- ---------------------------------------------------------------
-- 2. policy_review_queue — aggregated HR-visible items
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.policy_review_queue (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  question_hash   text NOT NULL,
  -- The agreed dedup key: (company_id, question_hash, sorted chunk_ids)
  -- We materialise the sorted-array string in a generated column so the
  -- UNIQUE constraint catches accidental dup inserts even if the app
  -- forgets to look up first.
  chunk_ids       uuid[] NOT NULL DEFAULT '{}',
  chunk_ids_key   text GENERATED ALWAYS AS (
    array_to_string(chunk_ids, ',')
  ) STORED,
  -- Short snippet of the assistant's answer (HR-visible). Always
  -- truncated to a few hundred chars at the app layer.
  response_summary text,
  -- Optional comment from the most recent negative-feedback row.
  latest_comment  text,
  feedback_count  integer NOT NULL DEFAULT 1
                    CHECK (feedback_count >= 1),
  priority        text NOT NULL DEFAULT 'normal'
                    CHECK (priority IN ('normal', 'high')),
  status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'in_review', 'resolved', 'dismissed')),
  first_seen_at   timestamptz NOT NULL DEFAULT now(),
  last_seen_at    timestamptz NOT NULL DEFAULT now(),
  resolved_by     uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  resolved_at     timestamptz,
  resolution_note text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.policy_review_queue IS
  '[P5-5] Aggregated HR review items derived from negative AI assistant feedback. Hard contract: HR is the only path that turns this into a policy_values change.';

-- One queue row per (company, question_hash, chunk_set). The generated
-- chunk_ids_key keeps this constraint readable in Postgres.
CREATE UNIQUE INDEX IF NOT EXISTS uq_policy_review_queue_dedup
  ON public.policy_review_queue (company_id, question_hash, chunk_ids_key);

CREATE INDEX IF NOT EXISTS idx_policy_review_queue_company_status_priority
  ON public.policy_review_queue (company_id, status, priority);

-- ---------------------------------------------------------------
-- 3. updated_at trigger for review_queue
-- ---------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at_review_queue()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_policy_review_queue_updated_at ON public.policy_review_queue;
CREATE TRIGGER trg_policy_review_queue_updated_at
  BEFORE UPDATE ON public.policy_review_queue
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at_review_queue();

-- ---------------------------------------------------------------
-- 4. RLS
-- ---------------------------------------------------------------
-- policy_feedback: any authenticated user can INSERT for their own
-- company; only HR/admin can SELECT (raw stream is internal).
ALTER TABLE public.policy_feedback ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS policy_feedback_insert_same_company ON public.policy_feedback;
CREATE POLICY policy_feedback_insert_same_company ON public.policy_feedback
  FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = (SELECT auth.uid())
        AND p.company_id = policy_feedback.company_id
    )
  );

DROP POLICY IF EXISTS policy_feedback_read_hr_admin ON public.policy_feedback;
CREATE POLICY policy_feedback_read_hr_admin ON public.policy_feedback
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = (SELECT auth.uid())
        AND p.company_id = policy_feedback.company_id
        AND p.role IN ('hr', 'admin')
    )
  );

-- policy_review_queue: HR + admin read+write within their company.
ALTER TABLE public.policy_review_queue ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS policy_review_queue_hr_admin_all ON public.policy_review_queue;
CREATE POLICY policy_review_queue_hr_admin_all ON public.policy_review_queue
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = (SELECT auth.uid())
        AND p.company_id = policy_review_queue.company_id
        AND p.role IN ('hr', 'admin')
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = (SELECT auth.uid())
        AND p.company_id = policy_review_queue.company_id
        AND p.role IN ('hr', 'admin')
    )
  );

COMMIT;
