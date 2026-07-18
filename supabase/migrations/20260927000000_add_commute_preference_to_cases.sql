-- AIQ-1603: single-select commute preference captured on the employee intake form.
-- Additive, nullable, no CHECK (the allowed enum is validated at the API DTO —
-- backend/app/schemas.py AssignmentContextDTO.commutePreference). No new table, so no
-- RLS/policy/REVOKE changes are required (public.cases already has them).
ALTER TABLE public.cases ADD COLUMN IF NOT EXISTS commute_preference text;
