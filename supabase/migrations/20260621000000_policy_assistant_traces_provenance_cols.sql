-- W2-5 provenance instrumentation — promote answer-provenance signals from
-- policy_assistant_traces.steps_json into queryable top-level columns so an HR
-- rollup (grounded% / refusal% / unverified count) can be computed per company
-- without JSON-walking every trace.
--
-- These mirror the values already computed by the answer pipelines:
--   * answer_kind          — policy_assistant_rag_engine (answer | refusal_*)
--                            and immigration_answer_engine.
--   * grounding_verdict     — verify_grounding() (grounded | partially_grounded |
--                            ungrounded). NULL when grounding was not run.
--   * verification_skipped  — verify_grounding() failed open (NULL/true).
--   * grounding_score       — verify_grounding() float 0-1, NULL when not run.
--
-- policy_assistant_traces is an EXISTING table (created in
-- 20260605000000_ai_unit_economics_reauthor.sql) with RLS already enabled and
-- locked to service_role only (REVOKE ALL FROM anon, authenticated, public).
-- This migration only ADDs columns + an index, so no new RLS/grant work is
-- required. Fully idempotent.

ALTER TABLE public.policy_assistant_traces
  ADD COLUMN IF NOT EXISTS answer_kind TEXT;

ALTER TABLE public.policy_assistant_traces
  ADD COLUMN IF NOT EXISTS grounding_verdict TEXT;

ALTER TABLE public.policy_assistant_traces
  ADD COLUMN IF NOT EXISTS verification_skipped BOOLEAN;

ALTER TABLE public.policy_assistant_traces
  ADD COLUMN IF NOT EXISTS grounding_score NUMERIC;

-- Rollup index for the per-company HR provenance widget: scope by tenant +
-- feature, slice by window (created_at), aggregate by answer_kind.
CREATE INDEX IF NOT EXISTS idx_pat_provenance_rollup
  ON public.policy_assistant_traces (company_id, feature_key, created_at, answer_kind);
