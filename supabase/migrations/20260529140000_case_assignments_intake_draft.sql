-- Persist the intake wizard's *form data* per assignment so a refresh
-- (or coming back the next day) restores everything the employee has
-- entered, not just the step counter from migration 20260529130000.
--
-- Choice of `case_assignments` (not `relocation_cases`):
--   The wizard is an employee-facing artifact. Drafts can diverge per
--   assignment for the same employee across multiple moves, and the
--   employee-ownership scope on case_assignments already restricts
--   reads/writes to the right user via RLS + endpoint scoping. Storing
--   on relocation_cases would mix HR-owned data with employee-edited
--   draft data and complicate ownership.
--
-- JSONB rather than normalized columns:
--   The wizard owns ~30 fields including nested arrays (members[]).
--   The frontend is the only writer/reader today, and the schema
--   evolves with the wizard. Normalizing would slow iteration without
--   a clear query-side benefit — we never search inside a draft.
--
-- No index: the only access pattern is "give me the draft for this
-- assignment_id" which is satisfied by the existing PK on case_assignments.id.
--
-- RLS: case_assignments already has RLS policies enforcing tenant
-- boundaries; new column inherits them. No new policy needed.

ALTER TABLE IF EXISTS public.case_assignments
  ADD COLUMN IF NOT EXISTS intake_draft jsonb NULL;
