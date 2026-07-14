-- [AIQ-1523] rfqs.created_by_user_id: uuid -> text
--
-- Completes the hotfix in 20260920000000. That migration dropped the FK to auth.users but left
-- the column typed `uuid`. ReloPass authenticates on legacy public.users, whose ids are TEXT
-- ("seed-emp-testingapril"), so every employee-created RFQ still died in prod with:
--
--     psycopg2.errors.InvalidTextRepresentation:
--     invalid input syntax for type uuid: "seed-emp-testingapril"
--
-- It only failed for EMPLOYEES: HR ids happen to be uuid-shaped, which is why one rfqs row
-- exists and the employee-led path has zero. Dropping the FK without retyping the column left
-- exactly the half of the bug that the employee-led model walks into.
--
-- Every sibling user column on this table family is already text — quotes.created_by_user_id,
-- rfqs.preferred_by_user_id, rfqs.validated_by_user_id — as are rfqs.case_id and (since
-- AIQ-1520) rfq_recipients.vendor_id and quotes.vendor_id. This column is the last uuid holdout.
--
-- uuid -> text is a widening cast: every existing value stays valid, and the one existing row
-- keeps its value verbatim. No policy, FK, or index depends on the column (verified against
-- prod), so the retype needs no drop/recreate dance.

BEGIN;

ALTER TABLE public.rfqs
    ALTER COLUMN created_by_user_id TYPE text USING created_by_user_id::text;

COMMENT ON COLUMN public.rfqs.created_by_user_id IS
  'The public.users id of whoever created the RFQ (employee or HR). TEXT, not uuid: legacy '
  'public.users ids are not uuid-shaped (AIQ-1523). Deliberately NOT FK-linked to auth.users — '
  'only ~1% of users are mirrored there.';

COMMIT;
