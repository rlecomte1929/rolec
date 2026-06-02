-- ─────────────────────────────────────────────────────────────────────────────
-- Parker Step G — Carbon + per-customer AI unit economics
-- ─────────────────────────────────────────────────────────────────────────────
-- Adds the ESG + TCO layer on top of the AI trace pipeline:
--   1. ai_model_energy_profiles — per-model energy/carbon constants (tokens → kWh →
--      gCO2e). New table → full RLS hard gate.
--   2. policy_assistant_traces — carbon + customer/feature attribution columns
--      (ALTER only; the table itself is bootstrapped by backend/database.py init_db()).
--   3. mv_ai_unit_economics — (week, customer_id, feature_key) cost/carbon rollup.
--
-- The admin rollup endpoint reads the BASE table (date-range parameterised, portable
-- PG+SQLite), NOT this matview, so the matview is a BI convenience off the request path.
--
-- DEPENDENCY / APPLY ORDER: section 2/3 below reference public.policy_assistant_traces,
-- which is created at runtime by backend/database.py init_db() (a legacy bootstrap
-- table, not a Supabase migration). Apply this migration only after the backend has
-- booted at least once against the target DB (prod already has the table). The ALTERs
-- are guarded with IF NOT EXISTS so re-application is safe.
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. Per-model energy / carbon profiles ────────────────────────────────────
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

DROP POLICY IF EXISTS ai_energy_admin_write ON public.ai_model_energy_profiles;
CREATE POLICY ai_energy_admin_write ON public.ai_model_energy_profiles
  FOR ALL TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS ai_energy_service_all ON public.ai_model_energy_profiles;
CREATE POLICY ai_energy_service_all ON public.ai_model_energy_profiles
  FOR ALL
  USING (auth.role() = 'service_role');

GRANT SELECT ON public.ai_model_energy_profiles TO authenticated;
REVOKE ALL ON public.ai_model_energy_profiles FROM anon;

COMMENT ON TABLE public.ai_model_energy_profiles IS
  'Parker Step G: per-model energy/carbon constants for tokens→kWh→gCO2e estimation (rough public estimates).';

-- ── 2. Carbon + attribution columns on the trace table ───────────────────────
-- policy_assistant_traces is bootstrapped by backend/database.py (legacy). ALTER it
-- additively so the matview below and the admin rollup can aggregate per customer/feature.
ALTER TABLE public.policy_assistant_traces ADD COLUMN IF NOT EXISTS co2e_grams_estimated NUMERIC;
ALTER TABLE public.policy_assistant_traces ADD COLUMN IF NOT EXISTS cost_usd_estimated   NUMERIC;
ALTER TABLE public.policy_assistant_traces ADD COLUMN IF NOT EXISTS tokens_in            INTEGER;
ALTER TABLE public.policy_assistant_traces ADD COLUMN IF NOT EXISTS tokens_out           INTEGER;
ALTER TABLE public.policy_assistant_traces ADD COLUMN IF NOT EXISTS customer_id          TEXT;
ALTER TABLE public.policy_assistant_traces ADD COLUMN IF NOT EXISTS feature_key          TEXT;

CREATE INDEX IF NOT EXISTS idx_pa_traces_customer_feature_created
  ON public.policy_assistant_traces (customer_id, feature_key, created_at);

-- ── 3. Unit-economics rollup (BI matview, off the request path) ───────────────
DROP MATERIALIZED VIEW IF EXISTS public.mv_ai_unit_economics;
CREATE MATERIALIZED VIEW public.mv_ai_unit_economics AS
SELECT
  date_trunc('week', created_at::timestamptz) AS week,
  customer_id,
  feature_key,
  count(*)                                    AS n_calls,
  coalesce(sum(cost_usd_estimated), 0)        AS total_cost_usd,
  coalesce(sum(tokens_in), 0)                 AS total_tokens_in,
  coalesce(sum(tokens_out), 0)                AS total_tokens_out,
  coalesce(sum(co2e_grams_estimated), 0)      AS total_co2e_grams
FROM public.policy_assistant_traces
WHERE feature_key IS NOT NULL
GROUP BY date_trunc('week', created_at::timestamptz), customer_id, feature_key;

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
