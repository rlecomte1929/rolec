-- Cleanup: remove the `la-*` neighbourhood-as-supplier shells.
--
-- Background: seed_suppliers_from_living_areas() (removed in the "Living Areas = 0"
-- rework) registered each `la-*` neighbourhood from living_areas.json as a
-- `living_areas` SUPPLIER, plus a matching service_catalog_items master, plus the
-- company_vendor_selections that referenced those masters. Neighbourhoods are now
-- advisory content (the engine ignores the registry + curation for living_areas), so
-- all of this is INERT — it only clutters admin supplier lists and is a latent footgun
-- (an approved `la-*` cap would re-introduce the field-poor shell). This removes it.
--
-- Data-only (no schema change). Idempotent: safe to re-run. Deletion order respects the
-- FKs discovered in prod:
--   * company_vendor_selections.master_item_id -> service_catalog_items (delete CVS first)
--   * service_catalog_items.supplier_id -> suppliers  [NO ACTION]  (delete catalog before suppliers)
--   * suppliers.id  <- supplier_service_capabilities / supplier_scoring_metadata /
--     vendor_metric_snapshots / provider_ratings  [ON DELETE CASCADE]  (auto-removed)
--
-- Pre-verified on prod: 0 rfq_recipients / quotes / provider_ratings / assignment_outcomes
-- reference any `la-*` id, so no live RFQ/quote/rating is affected.

BEGIN;

-- 1) Company curation rows pointing at the la-* living_areas catalog masters.
DELETE FROM public.company_vendor_selections
WHERE master_item_id IN (
  SELECT id FROM public.service_catalog_items
  WHERE category = 'living_areas' AND external_id LIKE 'la-%'
);

-- 2) The la-* living_areas catalog masters (NO ACTION FK to suppliers → must precede §3).
DELETE FROM public.service_catalog_items
WHERE category = 'living_areas' AND external_id LIKE 'la-%';

-- 3) The la-* supplier shells. Cascades to supplier_service_capabilities,
--    supplier_scoring_metadata, vendor_metric_snapshots, provider_ratings.
DELETE FROM public.suppliers
WHERE id LIKE 'la-%';

COMMIT;
