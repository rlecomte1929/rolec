-- AIQ-1311 PR2 — HR case-overview visibility.
--
-- hr_case_detail.get_case_overview reads origin_country_code / dest_country_code /
-- corridor / target_start_date from relocation_cases (via SELECT * in
-- db.get_relocation_case). But the table only had home_/host_country/city, so those
-- reads were always NULL and HR's Case Summary showed "Not provided" even after a
-- successful submit. Add the columns the reader expects; the submit promotion
-- (touch_relocation_case_route_from_wizard) now populates them.
--
-- No new table -> inherits relocation_cases' existing RLS (no new policy/REVOKE gate).
-- Idempotent. Applied OUT-OF-BAND per the migration workflow (CLAUDE.md) — merging
-- this PR does not create the columns in prod.

ALTER TABLE public.relocation_cases
  ADD COLUMN IF NOT EXISTS origin_country_code text,
  ADD COLUMN IF NOT EXISTS dest_country_code   text,
  ADD COLUMN IF NOT EXISTS origin_city         text,
  ADD COLUMN IF NOT EXISTS dest_city           text,
  ADD COLUMN IF NOT EXISTS target_start_date   date;

-- corridor is what the overview shows as the route; derive it from the codes so it
-- is always consistent and never needs a separate write.
ALTER TABLE public.relocation_cases
  ADD COLUMN IF NOT EXISTS corridor text
  GENERATED ALWAYS AS (origin_country_code || '-' || dest_country_code) STORED;
