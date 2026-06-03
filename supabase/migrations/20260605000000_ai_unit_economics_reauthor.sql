-- ─────────────────────────────────────────────────────────────────────────────
-- AIQ-754 — Re-author Parker Step G (AI unit economics + carbon) replay-safe.
-- ─────────────────────────────────────────────────────────────────────────────
-- Recovers the work dropped in PR #227 (commit 4a660e98), original file
-- 20260601080000_ai_unit_economics.sql. That migration was deferred + dropped
-- because it ALTERed public.policy_assistant_traces — a table that does NOT exist
-- on prod and has no creation path: backend/database.py init_db() returns at
-- line 1186 on Postgres before the SQLite-only CREATE TABLE scaffolding runs.
--
-- This re-author fixes the root cause by CREATING policy_assistant_traces as a
-- real Postgres table first, then layering on the energy-profiles table and the
-- unit-economics materialized view.
--
-- Idempotent (IF NOT EXISTS / DROP POLICY IF EXISTS / CREATE OR REPLACE / ON
-- CONFLICT DO NOTHING) so it applies clean to a fresh DB and no-ops on re-apply.
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. policy_assistant_traces — the missing prerequisite ─────────────────────
-- Column set + types are PG-grade but kept binding-compatible with the existing
-- writer (backend/database.py:14219, insert_policy_assistant_trace via psycopg2):
--   * id / created_at / steps_json: backend binds Python strings, which psycopg2
--     sends as unknown-typed literals → coerce cleanly into UUID / TIMESTAMPTZ /
--     JSONB via each type's input function.
--   * fallback_triggered stays INTEGER (the writer binds a bare int 1/0; Postgres
--     will NOT implicitly cast integer → boolean, so a BOOLEAN column would break
--     the insert).
-- The trailing columns (co2e/cost/tokens/customer/feature) are the Parker Step G
-- attribution + carbon fields the matview below aggregates.
CREATE TABLE IF NOT EXISTS public.policy_assistant_traces (
  id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id            TEXT,
  query_hash            TEXT        NOT NULL,
  company_id            TEXT        NOT NULL,
  steps_json            JSONB       NOT NULL DEFAULT '[]'::jsonb,
  total_latency_ms      INTEGER     NOT NULL DEFAULT 0,
  fallback_triggered    INTEGER     NOT NULL DEFAULT 0,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Parker Step G attribution + carbon columns:
  co2e_grams_estimated  NUMERIC,
  cost_usd_estimated    NUMERIC,
  tokens_in             INTEGER,
  tokens_out            INTEGER,
  customer_id           TEXT,
  feature_key           TEXT
);

CREATE INDEX IF NOT EXISTS idx_pa_traces_company_created
  ON public.policy_assistant_traces (company_id, created_at);

CREATE INDEX IF NOT EXISTS idx_pa_traces_session
  ON public.policy_assistant_traces (session_id)
  WHERE session_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_pa_traces_customer_feature_created
  ON public.policy_assistant_traces (customer_id, feature_key, created_at);

-- RLS hard gate (CLAUDE.md): traces hold per-company AI telemetry. The backend
-- reads/writes them over the service-role direct connection, so service-role-only
-- is the correct boundary — mirrors the rce.* canonical convention.
ALTER TABLE public.policy_assistant_traces ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS policy_assistant_traces_service_role_only ON public.policy_assistant_traces;
CREATE POLICY policy_assistant_traces_service_role_only
  ON public.policy_assistant_traces FOR ALL TO service_role
  USING (true) WITH CHECK (true);

REVOKE ALL ON public.policy_assistant_traces FROM anon, authenticated, public;
GRANT ALL ON public.policy_assistant_traces TO service_role;

COMMENT ON TABLE public.policy_assistant_traces IS
  'AIQ-754 / [P5-8]: one row per answer_policy_question() call. Raw query text is never stored (query_hash only). Parker Step G adds carbon + customer/feature attribution columns.';

-- ── 2. Per-model energy / carbon profiles ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ai_model_energy_profiles (
  model_name              TEXT        PRIMARY KEY,
  joules_per_input_token  NUMERIC     NOT NULL,
  joules_per_output_token NUMERIC     NOT NULL,
  region_gco2_per_kwh     NUMERIC     NOT NULL,   -- grid carbon intensity, gCO2e/kWh
  source_url              TEXT,                    -- citation for the estimate
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed rows. NOTE: vendor per-token energy is NOT published; these are rough public
-- estimates — the framework matters more than the precision today. Output tokens are
-- modelled as ~2× input cost (autoregressive decode dominates). Sources:
--   * Patterson et al. 2021, "Carbon Emissions and Large Neural Network Training".
--   * Luccioni et al. 2023, "Estimating the Carbon Footprint of BLOOM".
--   * ML CO2 Impact calculator (mlco2.github.io/impact).
--   * region default 400 gCO2e/kWh ≈ a mixed US/EU grid average (EU ~300, US ~370).
INSERT INTO public.ai_model_energy_profiles
  (model_name, joules_per_input_token, joules_per_output_token, region_gco2_per_kwh, source_url)
VALUES
  ('claude-sonnet-4-6',       0.40, 0.80, 400, 'https://mlco2.github.io/impact/ — frontier-class est.'),
  ('claude-haiku-4-5',        0.12, 0.24, 400, 'https://mlco2.github.io/impact/ — small-class est.'),
  ('gpt-4o',                  0.40, 0.80, 400, 'Patterson et al. 2021; mlco2.github.io/impact — frontier-class est.'),
  ('gpt-4o-mini',             0.12, 0.24, 400, 'mlco2.github.io/impact — small-class est.'),
  ('text-embedding-3-small',  0.05, 0.00, 400, 'mlco2.github.io/impact — embedding (no decode) est.')
ON CONFLICT (model_name) DO NOTHING;

-- RLS: readable by any authenticated user; writable only by platform admins.
ALTER TABLE public.ai_model_energy_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_energy_authenticated_select ON public.ai_model_energy_profiles;
CREATE POLICY ai_energy_authenticated_select ON public.ai_model_energy_profiles
  FOR SELECT TO authenticated
  USING (true);

-- Admin-write policy depends on public.is_admin(), which is defined out-of-band on
-- prod and is NOT present in repo migrations. Guard its creation so a fresh replay
-- (where the function may not yet exist) does not fail here. On prod the function
-- exists, so the policy is created. service_role writes are covered unconditionally
-- below regardless.
DROP POLICY IF EXISTS ai_energy_admin_write ON public.ai_model_energy_profiles;
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_proc
    WHERE proname = 'is_admin' AND pronamespace = 'public'::regnamespace
  ) THEN
    EXECUTE $pol$
      CREATE POLICY ai_energy_admin_write ON public.ai_model_energy_profiles
        FOR ALL TO authenticated
        USING (public.is_admin())
        WITH CHECK (public.is_admin())
    $pol$;
  END IF;
END $$;

DROP POLICY IF EXISTS ai_energy_service_all ON public.ai_model_energy_profiles;
CREATE POLICY ai_energy_service_all ON public.ai_model_energy_profiles
  FOR ALL
  USING (auth.role() = 'service_role');

GRANT SELECT ON public.ai_model_energy_profiles TO authenticated;
REVOKE ALL ON public.ai_model_energy_profiles FROM anon;

COMMENT ON TABLE public.ai_model_energy_profiles IS
  'Parker Step G: per-model energy/carbon constants for tokens→kWh→gCO2e estimation (rough public estimates).';

-- ── 3. Unit-economics rollup (BI matview, off the request path) ───────────────
DROP MATERIALIZED VIEW IF EXISTS public.mv_ai_unit_economics;
CREATE MATERIALIZED VIEW public.mv_ai_unit_economics AS
SELECT
  date_trunc('week', created_at)        AS week,
  customer_id,
  feature_key,
  count(*)                              AS n_calls,
  coalesce(sum(cost_usd_estimated), 0)  AS total_cost_usd,
  coalesce(sum(tokens_in), 0)           AS total_tokens_in,
  coalesce(sum(tokens_out), 0)          AS total_tokens_out,
  coalesce(sum(co2e_grams_estimated), 0) AS total_co2e_grams
FROM public.policy_assistant_traces
WHERE feature_key IS NOT NULL
GROUP BY date_trunc('week', created_at), customer_id, feature_key;

-- Unique index required for REFRESH ... CONCURRENTLY.
CREATE UNIQUE INDEX IF NOT EXISTS mv_ai_unit_economics_uidx
  ON public.mv_ai_unit_economics (week, customer_id, feature_key);

-- Admin-only: matviews cannot carry RLS, so REVOKE from anon + authenticated; the
-- admin route's is_admin() gate is the access boundary. service_role refreshes it.
REVOKE ALL ON public.mv_ai_unit_economics FROM anon;
REVOKE ALL ON public.mv_ai_unit_economics FROM authenticated;

CREATE OR REPLACE FUNCTION public.refresh_ai_unit_economics()
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_ai_unit_economics;
$$;

GRANT EXECUTE ON FUNCTION public.refresh_ai_unit_economics() TO service_role;

-- Suggested nightly refresh (pg_cron) — see G/RESULT.md:
--   SELECT cron.schedule('refresh_ai_unit_economics', '0 2 * * *',
--     $$ SELECT public.refresh_ai_unit_economics(); $$);
