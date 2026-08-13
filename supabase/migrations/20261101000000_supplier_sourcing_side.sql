-- [Stage 9 · Phase 1] Which side of the corridor each service category is sourced from.
--
-- ReloPass sources every category from the DESTINATION country. For movers that is backwards:
-- an international household-goods move is contracted from the ORIGIN agent, who surveys and
-- packs at origin and subcontracts the destination agent through their FIDI/IAM/OMNI network.
--
-- Addendum A §A.2. Nothing reads this column yet — the reader ships in a separate PR once this
-- is applied, per the migration-column-read rule.
BEGIN;

ALTER TABLE public.supplier_service_categories
  ADD COLUMN IF NOT EXISTS sourcing_side text NOT NULL DEFAULT 'destination';

ALTER TABLE public.supplier_service_categories
  DROP CONSTRAINT IF EXISTS supplier_service_categories_sourcing_side_check;

ALTER TABLE public.supplier_service_categories
  ADD CONSTRAINT supplier_service_categories_sourcing_side_check
  CHECK (sourcing_side IN ('origin', 'destination', 'both', 'either'));

COMMENT ON COLUMN public.supplier_service_categories.sourcing_side IS
  'Which end of the corridor a vendor for this category is engaged from. '
  'origin = contracted where the employee leaves (movers). '
  'destination = contracted where they arrive (the default, and correct for most). '
  'both = genuinely needed at each end (tax_finance: departure and arrival filings). '
  'either = one provider can serve from either end (rmc, healthcare_ipmi).';

-- The four that are not the default. The remaining seven — dsp, housing_agencies, schools,
-- banks, legal_admin, language_cultural, partner_family — keep 'destination'.
UPDATE public.supplier_service_categories SET sourcing_side = 'origin'
  WHERE code = 'movers';

UPDATE public.supplier_service_categories SET sourcing_side = 'both'
  WHERE code = 'tax_finance';

UPDATE public.supplier_service_categories SET sourcing_side = 'either'
  WHERE code IN ('rmc', 'healthcare_ipmi');

-- FLAGGED, deliberately left as 'destination': legal_admin is compliance_critical = true, and
-- an origin-country immigration lawyer is a real pattern for outbound advice. Addendum A §A.2
-- says destination; the build prompt says to flag rather than default silently. Change it in
-- its own migration if the product decision goes the other way.

COMMIT;
