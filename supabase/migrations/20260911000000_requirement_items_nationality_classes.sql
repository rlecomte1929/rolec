-- Nationality dimension for requirement_items.
--
-- The requirements engine keyed only on destination, so the FRANCE catalog --
-- which is the non-EEA salaried route (VLS-TS / ANEF / DGEF) -- was served to
-- every case regardless of nationality. A French citizen relocating home was
-- told to obtain a French work visa. The seed file already declared the right
-- scope in a comment ("EEA/EU nationals have free movement and need none of
-- this"); there was simply no column to enforce it.
--
-- Contract mirrors applies_to_assignment_types_json exactly:
--   NULL / absent  => the requirement applies to ALL nationality classes.
--   JSON array     => applies only to the listed classes.
-- Values: 'OWN_NATIONAL' | 'EU_EEA' | 'THIRD_COUNTRY'
-- (see backend/app/services/nationality_class.py)
--
-- Column add on an existing table: RLS and grants are already in force on
-- public.requirement_items, so no new policy is required here.

ALTER TABLE public.requirement_items
  ADD COLUMN IF NOT EXISTS applies_to_nationality_classes_json text;

COMMENT ON COLUMN public.requirement_items.applies_to_nationality_classes_json IS
  'JSON array of nationality classes this requirement applies to '
  '(OWN_NATIONAL | EU_EEA | THIRD_COUNTRY). NULL = applies to all.';
