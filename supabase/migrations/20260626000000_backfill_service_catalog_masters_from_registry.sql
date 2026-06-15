-- RECS-CATALOG-1 / AIQ-1079 — backfill the master catalog from the supplier registry.
--
-- service_catalog_items was empty platform-wide, so apply_hr_curation
-- (find_master_by_external_id) dropped every recommendation and EVERY employee
-- saw "HR is finalizing providers". This registers each active registry supplier
-- as a master keyed by external_id = suppliers.id (the id the recommendation
-- engine emits as item_id), so a registry rec maps to a master and HR can curate.
--
-- Decision (RECS-CATALOG-1, Option A): masters only — the strict opt-in contract
-- is preserved (employees still see only what HR has approved). This unblocks HR
-- to curate; it does not auto-approve anything.
--
-- Geo-agnostic by design: one master per (category, supplier), city = NULL. A
-- supplier serves multiple cities, and find_master_by_external_id keys on
-- (category, external_id) only; the curation view treats city-less masters as
-- applying everywhere, and the recommendation engine still filters candidates by
-- city via search_by_service_destination. No schema change; service_catalog_items
-- already has RLS. Idempotent (NOT EXISTS), source = 'seed'.

INSERT INTO public.service_catalog_items
  (id, category, city, country, name, attributes_json, source, active, external_id, created_at, updated_at)
SELECT
  gen_random_uuid(),
  cs.service_category,
  NULL,
  NULL,
  s.name,
  '{}'::jsonb,
  'seed',
  true,
  cs.supplier_id,
  now(),
  now()
FROM (
  SELECT DISTINCT service_category, supplier_id
  FROM public.supplier_service_capabilities
) cs
JOIN public.suppliers s ON s.id = cs.supplier_id AND s.status = 'active'
WHERE NOT EXISTS (
  SELECT 1 FROM public.service_catalog_items sci
  WHERE sci.category = cs.service_category AND sci.external_id = cs.supplier_id
);
