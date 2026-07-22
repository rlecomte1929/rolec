-- Cleanup: remove the two `living_areas` supplier shells that the la-* cleanup missed.
--
-- Background: cleanup_la_supplier_shells (20261001000000) removed the neighbourhood-as-
-- supplier shells seeded by seed_suppliers_from_living_areas() by keying on the `la-` id
-- prefix. Two `directory_import` rows use plain UUIDs, so they were missed and still carry
-- service_category='living_areas' in supplier_service_capabilities:
--   * 6236220c-b96a-4e9b-88ba-dcbf4d6ff862  NestFinders Europe   (nestfinders.eu)
--   * a1e80a3f-3049-48a8-80d3-b50d25f9b68a  BerlinReloc GmbH     (berlinreloc.de)
-- Both are directory_import, verified=false, capability platform_vetting_status='rejected',
-- coverage_scope_type='global', country_code NULL, and field-poor (no contact_email /
-- description). living_areas is advisory now (the recommendation engine renders it from
-- static/geo data and ignores the suppliers table), so these rows are inert — but they leave
-- 'living_areas' as a live SUPPLIER category when it should be empty (AIQ-1652).
--
-- Chosen action: DELETE (not re-categorise). These mirror exactly the la-* shells the prior
-- migration removed, are unreferenced (0 service_catalog_items / rfq_recipients /
-- company_vendor_selections — verified on prod 2026-07-22), and both are 'rejected' field-poor
-- imports with no single country (NestFinders is pan-European). Re-categorising rejected,
-- country-less junk into a real category (housing_agencies) would be worse taxonomy hygiene,
-- not better. Rollback = re-insert the two suppliers + their capability rows.
--
-- Data-only (no schema change). Idempotent: safe to re-run — once the shells are gone the
-- subqueries return no rows and every statement is a no-op. Same delete order as
-- cleanup_la_supplier_shells (FK-safe): company_vendor_selections -> service_catalog_items ->
-- suppliers (which cascades supplier_service_capabilities / supplier_scoring_metadata /
-- vendor_metric_snapshots / provider_ratings).
--
-- Scope guard: the supplier deletion targets only suppliers whose EVERY capability is
-- living_areas (bool_and), so a hypothetical multi-category supplier with a stray living_areas
-- row is never deleted. A final sweep (§4) drops any such residual capability row so the
-- category is provably empty regardless. Validated via rollback transaction on prod:
-- suppliers_deleted=2, living_areas_after=0, catalog_deleted=0, cvs_deleted=0.

BEGIN;

-- 1) Company curation rows pointing at any catalog master owned by these shells (0 on prod;
--    kept for FK safety + idempotency, mirroring cleanup_la_supplier_shells).
DELETE FROM public.company_vendor_selections
WHERE master_item_id IN (
  SELECT sci.id FROM public.service_catalog_items sci
  WHERE sci.supplier_id IN (
    SELECT supplier_id FROM public.supplier_service_capabilities
    GROUP BY supplier_id HAVING bool_and(service_category = 'living_areas')
  )
);

-- 2) Their catalog masters (NO ACTION FK to suppliers -> must precede §3).
DELETE FROM public.service_catalog_items
WHERE supplier_id IN (
  SELECT supplier_id FROM public.supplier_service_capabilities
  GROUP BY supplier_id HAVING bool_and(service_category = 'living_areas')
);

-- 3) The supplier shells whose ONLY capability is living_areas (NestFinders Europe,
--    BerlinReloc GmbH). Cascades their supplier_service_capabilities rows.
DELETE FROM public.suppliers
WHERE id IN (
  SELECT supplier_id FROM public.supplier_service_capabilities
  GROUP BY supplier_id HAVING bool_and(service_category = 'living_areas')
);

-- 4) Belt-and-braces: drop any remaining living_areas capability rows (multi-category
--    suppliers, if one ever exists), so the category is provably empty. No-op today.
DELETE FROM public.supplier_service_capabilities
WHERE service_category = 'living_areas';

COMMIT;
