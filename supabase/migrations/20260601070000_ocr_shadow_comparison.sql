-- ─────────────────────────────────────────────────────────────────────────────
-- Parker Step F — passport-OCR shadow comparison (GPT-4o vs self-hosted OSS)
-- ─────────────────────────────────────────────────────────────────────────────
-- SHADOW_COMPARE mode runs both passport extractors on the same image, returns
-- the GPT-4o result to the user, and logs per-field agreement + per-pipeline cost
-- here. No PII is stored — only field-level agreement booleans, MRZ checksum pass
-- flags, a disagreement count, and cost. An admin rollup endpoint reads this; the
-- materialized view below pre-aggregates it for BI.
--
-- RLS posture (CLAUDE.md hard gate): RLS enabled, admin SELECT via public.is_admin(),
-- service_role ALL, REVOKE ALL FROM anon.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.ocr_shadow_comparisons (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  case_id             TEXT,                       -- correlation only; nullable; no PII
  mrz_pass_gpt4o      BOOLEAN     NOT NULL DEFAULT false,
  mrz_pass_oss        BOOLEAN     NOT NULL DEFAULT false,
  field_agreement     JSONB       NOT NULL DEFAULT '{}'::jsonb,  -- {field: bool}
  compared_count      INTEGER     NOT NULL DEFAULT 0,
  agreed_count        INTEGER     NOT NULL DEFAULT 0,
  disagreement_count  INTEGER     NOT NULL DEFAULT 0,
  gpt4o_cost_usd      NUMERIC     NOT NULL DEFAULT 0,
  oss_cost_usd        NUMERIC     NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_ocr_shadow_created_at
  ON public.ocr_shadow_comparisons (created_at DESC);

-- ── Row Level Security ────────────────────────────────────────────────────────
ALTER TABLE public.ocr_shadow_comparisons ENABLE ROW LEVEL SECURITY;

-- Admin-only read (this is internal eval telemetry, not tenant data).
DROP POLICY IF EXISTS ocr_shadow_admin_select ON public.ocr_shadow_comparisons;
CREATE POLICY ocr_shadow_admin_select ON public.ocr_shadow_comparisons
  FOR SELECT TO authenticated
  USING (public.is_admin());

-- Service role full access (backend writes shadow rows through here).
DROP POLICY IF EXISTS ocr_shadow_service_all ON public.ocr_shadow_comparisons;
CREATE POLICY ocr_shadow_service_all ON public.ocr_shadow_comparisons
  FOR ALL
  USING (auth.role() = 'service_role');

GRANT SELECT ON public.ocr_shadow_comparisons TO authenticated;
REVOKE ALL ON public.ocr_shadow_comparisons FROM anon;

COMMENT ON TABLE public.ocr_shadow_comparisons IS
  'Parker Step F: per-image GPT-4o-vs-OSS passport-OCR shadow agreement telemetry (no PII).';

-- ─────────────────────────────────────────────────────────────────────────────
-- Materialized view — daily rollup for the (deferred) shadow dashboard.
--
-- NOTE: Postgres materialized views cannot carry RLS policies. Admin-only is
-- enforced by (a) REVOKE from anon + authenticated below, and (b) the admin API
-- route's is_admin() gate. The admin rollup endpoint itself reads the BASE TABLE
-- (parameterised by date range) rather than this view, so the view is a BI
-- convenience and is not on the request path.
-- ─────────────────────────────────────────────────────────────────────────────

DROP MATERIALIZED VIEW IF EXISTS public.mv_ocr_shadow_comparison;
CREATE MATERIALIZED VIEW public.mv_ocr_shadow_comparison AS
SELECT
  date_trunc('day', created_at)                                       AS day,
  count(*)                                                            AS n,
  round(
    sum(agreed_count)::numeric / nullif(sum(compared_count), 0), 4
  )                                                                   AS field_agreement_rate,
  round(
    sum(CASE WHEN mrz_pass_gpt4o THEN 1 ELSE 0 END)::numeric
      / nullif(count(*), 0), 4
  )                                                                   AS mrz_pass_rate_gpt4o,
  round(
    sum(CASE WHEN mrz_pass_oss THEN 1 ELSE 0 END)::numeric
      / nullif(count(*), 0), 4
  )                                                                   AS mrz_pass_rate_oss,
  round(avg(gpt4o_cost_usd)::numeric, 6)                              AS avg_cost_usd_gpt4o,
  round(avg(oss_cost_usd)::numeric, 6)                                AS avg_cost_usd_oss
FROM public.ocr_shadow_comparisons
GROUP BY date_trunc('day', created_at);

-- Unique index required for REFRESH ... CONCURRENTLY.
CREATE UNIQUE INDEX IF NOT EXISTS mv_ocr_shadow_comparison_day_uidx
  ON public.mv_ocr_shadow_comparison (day);

-- Admin-only: no anon/authenticated read of the view; service_role refreshes it.
REVOKE ALL ON public.mv_ocr_shadow_comparison FROM anon;
REVOKE ALL ON public.mv_ocr_shadow_comparison FROM authenticated;

-- Refresh helper (mirrors public.refresh_supplier_stats); called by a scheduled
-- Edge Function once the dashboard ships.
CREATE OR REPLACE FUNCTION public.refresh_ocr_shadow_comparison()
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_ocr_shadow_comparison;
$$;

GRANT EXECUTE ON FUNCTION public.refresh_ocr_shadow_comparison() TO service_role;
