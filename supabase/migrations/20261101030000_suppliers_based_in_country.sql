-- [Stage 9 · Phase 1] Where a supplier is BASED — the column Addendum A's eligibility rule
-- assumes and the schema did not have.
--
-- §S2 makes eligibility `vendor.based_in ∈ catchment.all`. Measured 2026-08-13, nothing could
-- answer that on the engine side:
--
--   suppliers.incorporation_country              0 of 108 populated
--   supplier_service_capabilities.country_code   means the country SERVED, not the base
--   service_catalog_items.country                981 of 985 — but only 62 link to a supplier
--
-- The proof that country_code is the served country, not the base: AGS France (SOFDI —
-- Société Française de Déménagement International) and Grospiron International are French
-- firms whose capability rows read 'DE' and 'NO'. Under a based-in reading, the data says two
-- French movers are German.
--
-- So the engine and the eval harness resolve vendor geography from two different tables. This
-- column gives the engine one to read. Reconciling it against service_catalog_items.country is
-- a Phase 2 eval — if they silently diverge, audit finding F-3 returns in a new shape.
--
-- Nullable on purpose. A guessed base country is the same class of error as a fabricated
-- accreditation, so the backfill leaves NULL wherever nothing evidences it, and the caller
-- treats NULL as "not eligible" rather than "eligible anywhere".
BEGIN;

ALTER TABLE public.suppliers
  ADD COLUMN IF NOT EXISTS based_in_country char(2);

ALTER TABLE public.suppliers
  DROP CONSTRAINT IF EXISTS suppliers_based_in_country_check;

-- ISO-3166-1 alpha-2, uppercase. Cheap guard against 'fr' or 'FRA' drifting in from a harvest.
ALTER TABLE public.suppliers
  ADD CONSTRAINT suppliers_based_in_country_check
  CHECK (based_in_country IS NULL OR based_in_country ~ '^[A-Z]{2}$');

COMMENT ON COLUMN public.suppliers.based_in_country IS
  'ISO2 country the supplier is BASED in — where it is registered and operates from. Distinct '
  'from supplier_service_capabilities.country_code, which is a country SERVED. NULL means '
  'unknown and is treated as not-eligible, never as eligible-anywhere. Populated only from '
  'evidence: a FIDI affiliate address, a SIREN, a Finanstilsynet register entry.';

CREATE INDEX IF NOT EXISTS idx_suppliers_based_in_country
  ON public.suppliers (based_in_country)
  WHERE based_in_country IS NOT NULL;

COMMIT;
