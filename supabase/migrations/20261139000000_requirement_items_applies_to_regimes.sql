-- requirement_items: social-security regime scope (additive, nullable).
-- case_requirement_checklist_state: A1/CoC filing lifecycle (additive, nullable).
--
-- `applies_to_regimes_json` is the posted (détaché) vs local (expatrié) axis that
-- assignment type already has: a JSON array such as ["posted"]. NULL ⇒ applies to
-- every regime. No backfill — existing rows keep today's meaning.
--
-- `filing_status` is per-case A1 lifecycle (not_required → required → filed →
-- issued → expired). NULL means the checklist has never recorded a filing state
-- (the boolean `completed` column is unchanged).
--
-- Additive only. Readers live in a follow-up PR after this is applied out of band.

ALTER TABLE public.requirement_items
    ADD COLUMN IF NOT EXISTS applies_to_regimes_json text;

COMMENT ON COLUMN public.requirement_items.applies_to_regimes_json IS
    'Optional JSON array of social-security regimes this requirement applies to '
    '(e.g. ["posted"]). NULL ⇒ applies to all. Fail-open, same contract as '
    'applies_to_assignment_types_json.';

ALTER TABLE public.case_requirement_checklist_state
    ADD COLUMN IF NOT EXISTS filing_status text;

COMMENT ON COLUMN public.case_requirement_checklist_state.filing_status IS
    'Optional A1/Certificate-of-Coverage lifecycle for this case+requirement: '
    'not_required, required, filed, issued, or expired. NULL until set.';
