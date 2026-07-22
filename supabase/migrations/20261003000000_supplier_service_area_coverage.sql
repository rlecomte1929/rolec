-- Real per-agency neighbourhood coverage — replaces the PR3 `area:*`-tag heuristic
-- that drove the housing-agency shortlist boost (Δ2). Which agency serves which
-- neighbourhood is supplier reference data (non-tenant), so it follows the
-- supplier_service_capabilities RLS pattern: authenticated read, service-role write,
-- anon revoked. Idempotent (safe to re-run / Preview replay).

CREATE TABLE IF NOT EXISTS public.supplier_service_area_coverage (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  supplier_id      text        NOT NULL,                       -- suppliers.id (e.g. ha-osl-p1)
  service_category text        NOT NULL DEFAULT 'housing_agencies',
  area_id          text        NOT NULL,                       -- living_areas item_id (e.g. la-o1)
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (supplier_id, service_category, area_id)
);
CREATE INDEX IF NOT EXISTS idx_ssac_supplier ON public.supplier_service_area_coverage (supplier_id);

ALTER TABLE public.supplier_service_area_coverage ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ssac_select ON public.supplier_service_area_coverage;
CREATE POLICY ssac_select ON public.supplier_service_area_coverage
  FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS ssac_service_all ON public.supplier_service_area_coverage;
CREATE POLICY ssac_service_all ON public.supplier_service_area_coverage
  FOR ALL TO service_role USING (true) WITH CHECK (true);

REVOKE ALL ON public.supplier_service_area_coverage FROM anon;

-- Seed the current Oslo agency → neighbourhood mapping (mirrors housing_agencies.json
-- `areas`). Idempotent; the app seed (seed_housing_agencies) keeps it in sync for
-- fresh environments and future agencies.
INSERT INTO public.supplier_service_area_coverage (supplier_id, service_category, area_id)
VALUES
  ('ha-osl-t1', 'housing_agencies', 'la-o4'),
  ('ha-osl-t1', 'housing_agencies', 'la-o1'),
  ('ha-osl-t2', 'housing_agencies', 'la-o2'),
  ('ha-osl-t2', 'housing_agencies', 'la-o5'),
  ('ha-osl-p1', 'housing_agencies', 'la-o1'),
  ('ha-osl-p1', 'housing_agencies', 'la-o3'),
  ('ha-osl-p2', 'housing_agencies', 'la-o5'),
  ('ha-osl-p2', 'housing_agencies', 'la-o2')
ON CONFLICT (supplier_id, service_category, area_id) DO NOTHING;
