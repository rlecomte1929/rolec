-- AIQ-1602 fix: HR/admin user ids in ReloPass are legacy TEXT values
-- (e.g. 'seed-hr-testingapril'), not uuids — the original uuid columns 500'd on
-- insert (the same uuid-vs-legacy-text-id trap that broke /api/notifications).
-- Widen the user-id columns to text. company_id stays uuid (real uuid tenant id).
-- Applied out-of-band to prod on 2026-07-18; this file reconciles the repo.
BEGIN;
ALTER TABLE public.hr_supplier_submissions ALTER COLUMN submitted_by_user_id TYPE text;
ALTER TABLE public.hr_supplier_submissions ALTER COLUMN reviewed_by TYPE text;
COMMIT;
