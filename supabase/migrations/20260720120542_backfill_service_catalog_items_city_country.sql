-- Ledger reconciliation (prod-as-oracle). Applied to prod out-of-band via MCP with no
-- repo file (fails migration-drift + `db push`). SQL recovered verbatim from
-- schema_migrations.statements. Idempotent by construction (only touches rows where
-- city IS NULL).

-- Backfill city and country on service_catalog_items from supplier_service_capabilities.
-- All three affected categories (schools, living_areas, movers) are covered.
-- DISTINCT ON (sci.id) with ORDER BY coverage_scope_type ASC ensures city-specific
-- records are preferred over global-coverage ones when a supplier covers multiple scopes.

UPDATE service_catalog_items sci
SET
  city       = src.city_name,
  country    = src.country_code,
  updated_at = now()
FROM (
  SELECT DISTINCT ON (sci2.id)
    sci2.id,
    cap.city_name,
    cap.country_code
  FROM service_catalog_items sci2
  JOIN supplier_service_capabilities cap
    ON  cap.supplier_id      = sci2.supplier_id
    AND cap.service_category = sci2.category
  WHERE sci2.city        IS NULL
    AND sci2.supplier_id IS NOT NULL
  ORDER BY sci2.id, cap.coverage_scope_type ASC  -- 'city' sorts before 'global'
) src
WHERE sci.id = src.id;
