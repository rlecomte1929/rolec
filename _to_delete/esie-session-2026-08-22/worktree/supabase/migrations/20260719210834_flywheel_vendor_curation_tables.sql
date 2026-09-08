-- Ledger reconciliation (prod-as-oracle). Applied to prod out-of-band via MCP with no
-- repo file (fails migration-drift + `db push`). SQL recovered verbatim from
-- schema_migrations.statements; CREATE POLICY statements are preceded by DROP POLICY
-- IF EXISTS so a fresh Preview replay is idempotent.

-- ── vendor_curation_runs ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.vendor_curation_runs (
  id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  corridor          text        NOT NULL,
  service_category  text        NOT NULL,
  run_date          timestamptz NOT NULL DEFAULT now(),
  sources_searched  jsonb       NOT NULL DEFAULT '[]',
  candidates_found  integer     NOT NULL DEFAULT 0,
  promoted_count    integer     NOT NULL DEFAULT 0,
  status            text        NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued','searching','staged','reviewed','completed','failed')),
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.vendor_curation_runs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.vendor_curation_runs FROM anon;
DROP POLICY IF EXISTS svc_all_curation_runs ON public.vendor_curation_runs;
CREATE POLICY svc_all_curation_runs ON public.vendor_curation_runs
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ── vendor_candidates ─────────────────────────────────────────────────────
-- Note: promoted_supplier_id is text to match suppliers.id (varchar, e.g. 'no-mv-1')
CREATE TABLE IF NOT EXISTS public.vendor_candidates (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id                uuid        REFERENCES public.vendor_curation_runs(id) ON DELETE SET NULL,
  name                  text        NOT NULL,
  website_url           text,
  email                 text,
  city                  text,
  country_code          text,
  service_category      text        NOT NULL,
  source_url            text,
  source_name           text,
  source_tier           integer     CHECK (source_tier BETWEEN 1 AND 3),
  confidence_score      numeric(3,2) CHECK (confidence_score BETWEEN 0 AND 1),
  bar_registered        boolean,    -- regulated categories only; NULL otherwise
  notes                 text,
  status                text        NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','approved','rejected','duplicate','needs_reverification')),
  promoted_supplier_id  text,       -- set once promoted into suppliers (matches suppliers.id type)
  reviewed_by           text,
  reviewed_at           timestamptz,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.vendor_candidates ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.vendor_candidates FROM anon;
DROP POLICY IF EXISTS svc_all_candidates ON public.vendor_candidates;
CREATE POLICY svc_all_candidates ON public.vendor_candidates
  FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE INDEX IF NOT EXISTS idx_candidates_status         ON public.vendor_candidates (status);
CREATE INDEX IF NOT EXISTS idx_candidates_corridor_cat   ON public.vendor_candidates (service_category, country_code);

-- ── corridor_coverage_targets ─────────────────────────────────────────────
-- coverage_status: gap <3 | partial 3–4 | covered ≥5
CREATE TABLE IF NOT EXISTS public.corridor_coverage_targets (
  id                     uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  corridor               text        NOT NULL,
  service_category       text        NOT NULL,
  target_vendor_count    integer     NOT NULL DEFAULT 5,
  current_verified_count integer     NOT NULL DEFAULT 0,
  demand_case_count      integer     NOT NULL DEFAULT 0,
  coverage_status        text        NOT NULL DEFAULT 'gap'
                           CHECK (coverage_status IN ('gap','partial','covered')),
  last_updated           timestamptz NOT NULL DEFAULT now(),
  UNIQUE (corridor, service_category)
);
ALTER TABLE public.corridor_coverage_targets ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.corridor_coverage_targets FROM anon;
DROP POLICY IF EXISTS svc_all_coverage ON public.corridor_coverage_targets;
CREATE POLICY svc_all_coverage ON public.corridor_coverage_targets
  FOR ALL TO service_role USING (true) WITH CHECK (true);
