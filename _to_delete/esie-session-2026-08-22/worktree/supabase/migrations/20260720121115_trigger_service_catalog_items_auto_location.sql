-- Ledger reconciliation (prod-as-oracle). Applied to prod out-of-band via MCP with no
-- repo file (fails migration-drift + `db push`). SQL recovered verbatim from
-- schema_migrations.statements; CREATE OR REPLACE FUNCTION is idempotent and the
-- trigger is preceded by DROP TRIGGER IF EXISTS so a fresh Preview replay is idempotent.

-- Trigger: auto-populate city/country on service_catalog_items from supplier_service_capabilities.
-- Fires BEFORE INSERT so the row is corrected before it lands in the table.
-- Prefers city-specific capability rows over country/global rows.
-- Only activates when city IS NULL and supplier_id IS NOT NULL — safe to be idempotent.

CREATE OR REPLACE FUNCTION service_catalog_items_auto_location()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_city    text;
  v_country text;
BEGIN
  -- Only act when location is absent and a supplier link exists
  IF NEW.city IS NOT NULL OR NEW.supplier_id IS NULL THEN
    RETURN NEW;
  END IF;

  -- Prefer city-specific rows; fall back to country/global if no city row exists
  SELECT
    cap.city_name,
    cap.country_code
  INTO v_city, v_country
  FROM supplier_service_capabilities cap
  WHERE cap.supplier_id      = NEW.supplier_id
    AND cap.service_category = NEW.category
  ORDER BY
    -- 'city' < 'country' < 'global' alphabetically, so ASC puts city first
    cap.coverage_scope_type ASC,
    cap.created_at ASC
  LIMIT 1;

  IF FOUND THEN
    NEW.city    := v_city;      -- may remain NULL for country/global scope rows — that is intentional
    NEW.country := COALESCE(NEW.country, v_country);
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_service_catalog_items_auto_location ON service_catalog_items;
CREATE TRIGGER trg_service_catalog_items_auto_location
BEFORE INSERT ON service_catalog_items
FOR EACH ROW
EXECUTE FUNCTION service_catalog_items_auto_location();
