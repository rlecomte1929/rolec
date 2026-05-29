-- ============================================================
-- S4 Spike: Family details propagation
-- Adds structured family data to wizard_cases so the plan
-- generation layer can determine family workstreams without
-- re-asking profile questions.
--
-- touch policy: ADD COLUMN IF NOT EXISTS on wizard_cases only.
-- No existing columns are modified.
-- ============================================================

-- 1. family_details JSONB: spouse and child data captured during intake.
--    Schema (stored as JSONB, validated at application layer):
--    {
--      "hasSpouse": true,
--      "spouseFullName": "Marie Dupont",
--      "spouseNationality": "French",
--      "spouseNationalityIsoCode": "FR",
--      "spouseIsEuCitizen": true,
--      "spouseEmploymentIntent": "yes",   -- yes | no | unknown
--      "partnerVisaStatus": "eu_citizen", -- eu_citizen | non_eu_with_permit | non_eu_no_permit | unknown
--      "childCount": 2,
--      "children": [
--        {"firstName": "Emma", "dateOfBirth": "2016-03-12", "nationality": "French"},
--        {"firstName": "Lucas", "dateOfBirth": "2019-07-04", "nationality": "French"}
--      ]
--    }
ALTER TABLE public.wizard_cases
  ADD COLUMN IF NOT EXISTS family_details JSONB DEFAULT '{}'::jsonb;

-- 2. Computed convenience columns — populated by a trigger or application layer.
--    These allow cheap SQL filtering without JSONB extraction on every query.

-- has_spouse: quick filter for "does this case have a travelling spouse?"
ALTER TABLE public.wizard_cases
  ADD COLUMN IF NOT EXISTS has_spouse BOOLEAN DEFAULT FALSE;

-- child_count: integer shortcut; avoids JSONB array length query in list views
ALTER TABLE public.wizard_cases
  ADD COLUMN IF NOT EXISTS child_count INTEGER DEFAULT 0;

-- partner_requires_visa: true when spouse/partner is non-EU and destination is EU
--   (or any case where a separate family visa is needed).
--   Set by application layer during intake; used to gate the partner_mvv workstream.
ALTER TABLE public.wizard_cases
  ADD COLUMN IF NOT EXISTS partner_requires_visa BOOLEAN DEFAULT FALSE;

-- 3. Indexes for common family-related filters
CREATE INDEX IF NOT EXISTS idx_wizard_cases_has_spouse
  ON public.wizard_cases (has_spouse);

CREATE INDEX IF NOT EXISTS idx_wizard_cases_child_count
  ON public.wizard_cases (child_count);

-- ============================================================
-- Verification query (run manually after applying):
--   SELECT id, has_spouse, child_count, partner_requires_visa,
--          family_details
--   FROM wizard_cases
--   LIMIT 10;
-- ============================================================
