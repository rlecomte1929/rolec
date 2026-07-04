-- =============================================================================
-- Supplier Catalog GAP 1: Source provenance + per-capability vetting lifecycle
--
-- Adds provenance to the supplier entity and a review lifecycle to each service
-- offering, replacing the coarse `verified` boolean with an auditable workflow.
--
-- No new tables → the RLS hard gate does not apply; the existing suppliers /
-- supplier_service_capabilities policies (20260312100000_supplier_registry.sql)
-- already scope correctly (authenticated SELECT + service_role ALL).
--
-- `vetted_by` is text (not uuid): ReloPass session user ids are legacy varchars,
-- not Supabase auth uuids, so a uuid column would reject valid actor ids.
-- =============================================================================

BEGIN;

-- Source provenance on the supplier entity
ALTER TABLE public.suppliers
  ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'admin_manual'
    CHECK (source IN ('admin_manual', 'customer_upload', 'scraper_discovery', 'directory_import')),
  ADD COLUMN IF NOT EXISTS source_url text NULL,
  ADD COLUMN IF NOT EXISTS source_reference text NULL;

-- Per-service-offering vetting lifecycle
ALTER TABLE public.supplier_service_capabilities
  ADD COLUMN IF NOT EXISTS platform_vetting_status text NOT NULL DEFAULT 'pending'
    CHECK (platform_vetting_status IN ('pending', 'approved', 'rejected', 'suspended')),
  ADD COLUMN IF NOT EXISTS vetted_by text NULL,
  ADD COLUMN IF NOT EXISTS vetted_at timestamptz NULL,
  ADD COLUMN IF NOT EXISTS vetting_notes text NULL;

CREATE INDEX IF NOT EXISTS idx_supplier_capabilities_vetting
  ON public.supplier_service_capabilities (platform_vetting_status);

-- Backfill: existing capabilities of active suppliers are treated as approved so
-- nothing that is live today disappears from recommendations. Guarded on the
-- default so the migration is safely re-runnable.
UPDATE public.supplier_service_capabilities ssc
SET platform_vetting_status = 'approved'
FROM public.suppliers s
WHERE ssc.supplier_id = s.id
  AND s.status = 'active'
  AND ssc.platform_vetting_status = 'pending';

COMMIT;
