-- [ANDREA-P1] Admin "Delete selected" on /admin/assignments sets status='archived'
-- (AdminAssignments.tsx) and the list filters already treat 'archived' as inactive
-- (backend/db/cases.py: NOT IN ('archived','closed')), but the CHECK constraint on
-- case_assignments.status never admitted it, so every archive attempt failed with
-- IntegrityError -> HTTP 500 ("Failed to update assignment status: CheckViolation").
-- Observed 2026-09-12 while closing Andrea Peinado's duplicate cases.
--
-- Widen the constraint to the statuses the application actually writes. Existing rows
-- are untouched (the old set is a strict subset).

ALTER TABLE public.case_assignments
    DROP CONSTRAINT IF EXISTS case_assignments_status_check;

ALTER TABLE public.case_assignments
    ADD CONSTRAINT case_assignments_status_check
    CHECK (status = ANY (ARRAY[
        'created'::text,
        'assigned'::text,
        'awaiting_intake'::text,
        'submitted'::text,
        'approved'::text,
        'rejected'::text,
        'closed'::text,
        'archived'::text
    ]));
