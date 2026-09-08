-- ============================================================
-- S3 Spike: contract_type + move_type discriminator
-- Adds the columns that gate plan scope and scenario classification
-- for all 8 persona test cases.
--
-- touch policy: ADD COLUMN IF NOT EXISTS on wizard_cases only.
-- No existing columns are modified.
-- ============================================================

-- 1. contract_type: what kind of employment arrangement is this?
--    Values mirror the CaseType enum in relocation_classifier.py
ALTER TABLE public.wizard_cases
  ADD COLUMN IF NOT EXISTS contract_type TEXT
    CHECK (contract_type IN (
      'lta',              -- long-term assignment (12–36 months), employer-sponsored
      'permanent_transfer', -- no planned return date, full relocation
      'short_term_project', -- < 6 months, may not require full work permit
      'domestic_move',    -- same country, different city — NO immigration workstream
      'repatriation',     -- returning to home country
      'remote_worker',    -- works remotely from destination, no employer sponsorship
      'self_employed',    -- contractor / freelancer
      'student',          -- student visa route
      'unknown'           -- default until classified
    ));

-- 2. move_type: international vs domestic vs return — the coarse discriminator
ALTER TABLE public.wizard_cases
  ADD COLUMN IF NOT EXISTS move_type TEXT
    CHECK (move_type IN (
      'international',  -- crosses a national border
      'domestic',       -- same country (suppresses immigration phase)
      'return'          -- repatriation to home country
    ));

-- 3. assignment_start_date: when does the work arrangement begin?
--    Used to backdate visa petition timelines (e.g., US L1B: file 6 months before)
ALTER TABLE public.wizard_cases
  ADD COLUMN IF NOT EXISTS assignment_start_date DATE;

-- 4. assignment_end_date: when is the assignment scheduled to end?
--    The date_trigger_service checks this to fire repat_due events (Scenario 7)
ALTER TABLE public.wizard_cases
  ADD COLUMN IF NOT EXISTS assignment_end_date DATE;

-- 5. target_arrival_date: when does the person want to be in their new home?
--    Distinct from target_move_date (which is the shipping/logistics date).
--    Used as the primary backdate anchor for immigration timelines.
ALTER TABLE public.wizard_cases
  ADD COLUMN IF NOT EXISTS target_arrival_date DATE;

-- 6. Index on contract_type for plan generation queries that filter by type
CREATE INDEX IF NOT EXISTS idx_wizard_cases_contract_type
  ON public.wizard_cases (contract_type);

-- 7. Index on move_type for quick domestic-move suppression check
CREATE INDEX IF NOT EXISTS idx_wizard_cases_move_type
  ON public.wizard_cases (move_type);

-- 8. Default existing rows to 'unknown' / 'international' so existing
--    data doesn't break any NOT NULL checks added later.
--    (Columns are nullable for now; this UPDATE is a safety net for any
--    code that does IS NOT NULL checks.)
UPDATE public.wizard_cases
  SET contract_type = 'unknown'
  WHERE contract_type IS NULL;

UPDATE public.wizard_cases
  SET move_type = 'international'
  WHERE move_type IS NULL
    AND (origin_country IS DISTINCT FROM dest_country OR dest_country IS NULL);

UPDATE public.wizard_cases
  SET move_type = 'domestic'
  WHERE move_type IS NULL
    AND origin_country IS NOT NULL
    AND dest_country IS NOT NULL
    AND origin_country = dest_country;

-- ============================================================
-- Verification query (run manually after applying):
--   SELECT id, origin_country, dest_country, contract_type, move_type
--   FROM wizard_cases
--   LIMIT 20;
-- ============================================================
