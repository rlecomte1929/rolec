-- Pre-fill destination + origin *city* in the employee wizard, the same
-- way host_country / home_country pre-fill the country. Before this,
-- the wizard's dest_city was empty for every case because there was no
-- column to read it from — only the free-text `profile_json.movePlan.*`
-- which is unreliable seed data.
--
-- Both columns are nullable: HR will populate them via the case wizard
-- in a follow-up commit. Once set, the employee opens the wizard and
-- sees both country and city pre-filled and locked as "HR pre-filled".
--
-- No index — the only access path is "give me the destination payload
-- for this case row", which is already covered by the case's PK.
-- relocation_cases already has RLS; the new columns inherit it.

ALTER TABLE IF EXISTS public.relocation_cases
  ADD COLUMN IF NOT EXISTS host_city text NULL,
  ADD COLUMN IF NOT EXISTS home_city text NULL;
