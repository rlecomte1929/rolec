-- [NAV-SP-2 Tier 3] Vendor metric snapshots — historical aggregates for trends.
--
-- supplier_scoring_metadata stores only the *current* average_rating / price, so
-- the Vendor Performance dashboard cannot draw real "is cost rising / are reviews
-- improving" trend lines. This table captures one row per (supplier × service
-- category × day) so the dashboard can plot change over time and the watchlist
-- can compute ▲/▼ deltas.
--
-- Write path: a nightly cron (POST /api/crons/snapshot-vendor-metrics) runs via
-- the backend service role (SessionLocal), which bypasses RLS. The frontend never
-- reads this table directly — it goes through GET /api/hr/vendor-performance. So
-- the RLS policy below is defense-in-depth (anon revoked + admin read), matching
-- the "global vendor data, internal-only" boundary (suppliers carry no org_id).
--
-- Security hard gates (CLAUDE.md): RLS enabled + scoped policy + REVOKE anon.

CREATE TABLE IF NOT EXISTS public.vendor_metric_snapshots (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  supplier_id      text NOT NULL REFERENCES public.suppliers(id) ON DELETE CASCADE,
  service_category text NOT NULL,
  captured_date    date NOT NULL DEFAULT CURRENT_DATE,
  avg_rating       numeric,
  avg_cost_eur     integer,
  review_count     integer,
  created_at       timestamptz NOT NULL DEFAULT now(),
  -- Idempotency: one snapshot per supplier per category per day. The cron upserts
  -- on this key so a same-day re-run updates rather than duplicates.
  CONSTRAINT uq_vendor_metric_snapshots_supplier_cat_date
    UNIQUE (supplier_id, service_category, captured_date)
);

COMMENT ON TABLE public.vendor_metric_snapshots IS
  '[NAV-SP-2] Daily per-supplier-per-category aggregate snapshots (rating, cost, review_count) powering the Vendor Performance trend charts. Written by the snapshot-vendor-metrics cron (service role).';

CREATE INDEX IF NOT EXISTS idx_vendor_metric_snapshots_supplier
  ON public.vendor_metric_snapshots (supplier_id);
CREATE INDEX IF NOT EXISTS idx_vendor_metric_snapshots_date
  ON public.vendor_metric_snapshots (captured_date);
CREATE INDEX IF NOT EXISTS idx_vendor_metric_snapshots_category
  ON public.vendor_metric_snapshots (service_category);

ALTER TABLE public.vendor_metric_snapshots ENABLE ROW LEVEL SECURITY;

-- Admin: read-only across all snapshots (operational visibility). HR reads happen
-- server-side via the service role through /api/hr/vendor-performance, not via
-- PostgREST, so no authenticated/HR direct-read policy is required. Writes are
-- service-role only (RLS-bypassing), so there is no INSERT/UPDATE policy.
DROP POLICY IF EXISTS "vendor_metric_snapshots_admin_read" ON public.vendor_metric_snapshots;
CREATE POLICY "vendor_metric_snapshots_admin_read" ON public.vendor_metric_snapshots
  FOR SELECT
  USING (public.is_admin());

-- Defense-in-depth: the anon key (shipped in the frontend bundle) must never
-- reach this table directly via PostgREST.
REVOKE ALL ON public.vendor_metric_snapshots FROM anon;
