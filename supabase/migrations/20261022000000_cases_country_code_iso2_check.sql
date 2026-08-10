-- [AIQ-1778] public.cases country columns must be ISO 3166-1 alpha-2.
--
-- Why a constraint and not just a backfill: the columns are plain `text` with no CHECK, no
-- domain and no FK, while every neighbouring column that mattered got one (`purpose`, `status`,
-- `stage`, `risk_level`). Countries were left open and prod accumulated 25 bad origins and
-- 15 bad destinations -- 'France' x22, 'Germany', 'India', and one empty string.
--
-- The readers are unforgiving, and they fail SILENTLY:
--   * trigger_engine._build_context upper-cases without shortening, so 'France' -> 'FRANCE',
--     misses the pure-ISO-2 _EEA_COUNTRIES frozenset, and visa_type resolves to
--     'skilled_worker' instead of 'eea_registration'. The affected employees were matched to
--     BLUE-CARD and WORK-VISA-DE -- EU citizens handed third-country-national paperwork --
--     while RP-NO-DATASHEET, gated on eea_registration, never attached.
--   * immigration_requirement_service matched no corridor and returned ZERO requirements,
--     which reads as "nothing required". A fail-open.
--   * `corridor` is a STORED GENERATED column (origin || '-' || dest), so those rows carried
--     corridor = 'France-Norway'.
--
-- Data was normalised out-of-band on 2026-08-10 before this migration was written (152
-- column-values across public.cases and public.relocation_cases; a permitted non-schema
-- backfill). Verified immediately afterwards: 0 values failing '^[A-Z]{2}$' in either table,
-- and 0 corridors failing '^[A-Z]{2}-[A-Z]{2}$'. So these constraints validate on apply.
-- The writer was fixed in the same change -- backend/db/cases.py now resolves both countries
-- through requirements_country_key.to_iso_alpha2 and skips the upsert rather than storing an
-- unusable value.
--
-- Shape, not membership. '^[A-Z]{2}$' deliberately accepts a well-formed code we hold no data
-- for (Monaco, or the 'ZZ'/'QQ' placeholders test_hr_case_detail_feasibility.py uses). Whether
-- we have requirement coverage for a country is a different question, owned by
-- requirements_country_key.to_iso. Constraining membership here would block real cases.
--
-- NOT NULL does not exclude '': the empty-string row proved that, so the regex carries the load.
--
-- Follow-up, deliberately NOT done here: public.relocation_cases has the same four columns and
-- was backfilled too, but its writers (db/cases.py upsert_relocation_case ~1831 and
-- update_relocation_case_host_country ~2849) still take the country as an unnormalised caller
-- parameter. Adding a CHECK there before normalising them would convert a silent data-quality
-- problem into a hard failure on HR case creation. Normalise those two writers first.
--
-- Pattern copied from public.case_outcomes (20260620100000_case_outcomes.sql:28), the one table
-- that already got this right.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'cases_origin_country_code_iso2_chk'
  ) THEN
    ALTER TABLE public.cases
      ADD CONSTRAINT cases_origin_country_code_iso2_chk
      CHECK (origin_country_code ~ '^[A-Z]{2}$');
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'cases_dest_country_code_iso2_chk'
  ) THEN
    ALTER TABLE public.cases
      ADD CONSTRAINT cases_dest_country_code_iso2_chk
      CHECK (dest_country_code ~ '^[A-Z]{2}$');
  END IF;
END $$;

COMMENT ON COLUMN public.cases.origin_country_code IS
  'ISO 3166-1 alpha-2, UPPERCASE. Enforced by cases_origin_country_code_iso2_chk. Never a country name: trigger_engine matches _EEA_COUNTRIES by exact 2-letter membership, so a name silently resolves the wrong visa_type. Normalise with requirements_country_key.to_iso_alpha2 before writing.';

COMMENT ON COLUMN public.cases.dest_country_code IS
  'ISO 3166-1 alpha-2, UPPERCASE. Enforced by cases_dest_country_code_iso2_chk. See origin_country_code.';
