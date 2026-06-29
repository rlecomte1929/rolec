-- ─────────────────────────────────────────────────────────────────────────────
-- Phase 1 keystone — ai_replay_records: masked, replayable record of every
-- immigration answer / AI roadmap generation, so the offline grader can re-grade
-- past outputs without re-running the LLM.
-- ─────────────────────────────────────────────────────────────────────────────
-- policy_assistant_traces deliberately stores only query_hash + cited_chunk_ids
-- (never prompt/output) per PII policy. That makes offline grading and
-- feedback→gold-case conversion impossible. This table closes the gap WITHOUT
-- re-introducing the leak: the writer (backend/app/services/ai_replay_store.py)
-- runs query + output through pii_masker.mask_pii() before insert, so only
-- [REDACTED_*]-masked text lands here. retrieved_chunk_ids point at
-- immigration_corpus_chunks (published authority source text — not personal data).
--
-- Idempotent (IF NOT EXISTS / DROP POLICY IF EXISTS). Applies clean to a fresh DB
-- and no-ops on re-apply.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.ai_replay_records (
  id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  trace_id              TEXT,
  feature_key           TEXT        NOT NULL,
  corridor              TEXT,
  -- PII-masked input + output (mask_pii applied by the writer BEFORE insert).
  query_masked          TEXT,
  output_masked         TEXT,
  -- Chunk ids the answer/roadmap was grounded on. Authority source text, not PII.
  retrieved_chunk_ids   JSONB       NOT NULL DEFAULT '[]'::jsonb,
  -- Prompt attribution (Parker Step D) — which registry version/arm served this.
  prompt_version_id     TEXT,
  canary_arm            TEXT,
  -- Pipeline outcome: OK / RULE_NOT_FOUND / refusal_* and the verifier verdict.
  result                TEXT,
  approved              INTEGER     NOT NULL DEFAULT 0,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Grader reads newest-first, scoped by feature + corridor.
CREATE INDEX IF NOT EXISTS idx_ai_replay_feature_corridor_created
  ON public.ai_replay_records (feature_key, corridor, created_at);

-- Join back from a trace (and from ai_human_feedback.trace_session_id) to the
-- replay record that produced the graded output.
CREATE INDEX IF NOT EXISTS idx_ai_replay_trace
  ON public.ai_replay_records (trace_id)
  WHERE trace_id IS NOT NULL;

-- RLS hard gate (CLAUDE.md): replay records hold masked AI I/O. The backend
-- reads/writes over the service-role direct connection — service-role-only is the
-- correct boundary, mirroring policy_assistant_traces.
ALTER TABLE public.ai_replay_records ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_replay_records_service_role_only ON public.ai_replay_records;
CREATE POLICY ai_replay_records_service_role_only
  ON public.ai_replay_records FOR ALL TO service_role
  USING (true) WITH CHECK (true);

REVOKE ALL ON public.ai_replay_records FROM anon, authenticated, public;
GRANT ALL ON public.ai_replay_records TO service_role;

COMMENT ON TABLE public.ai_replay_records IS
  'Masked, replayable record of immigration-answer / AI-roadmap generations for offline grading (Phase 1 eval keystone). query_masked/output_masked are mask_pii-redacted before insert; service-role only.';
