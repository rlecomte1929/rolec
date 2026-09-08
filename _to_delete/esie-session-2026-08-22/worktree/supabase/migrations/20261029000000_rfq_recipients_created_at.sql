-- [AIQ-1819] rfq_recipients.created_at — the column _vendor_names_for_rfq has always ordered by
--
-- backend/db/vendors.py:533 (`_vendor_names_for_rfq`) runs:
--
--     SELECT s.name FROM rfq_recipients rr
--     LEFT JOIN suppliers s ON s.id = rr.vendor_id
--     WHERE rr.rfq_id = :r ORDER BY rr.created_at
--
-- The column does not exist, so Postgres raises 42703 every single time. Reproduced against
-- production 2026-08-11:  ERROR: 42703: column rr.created_at does not exist
--
-- It is reachable — vendors.py:608, inside list_quote_conversations_for_employee, a live
-- employee path. Nobody noticed because the function ends `except Exception: return None` and
-- the call site reads `or "Service provider"`, so every employee quote thread has always shown
-- the generic label instead of the vendor's name. The feature has never worked once.
--
-- WHY A NEW COLUMN RATHER THAN REUSING AN EXISTING ONE
-- ----------------------------------------------------
-- Nothing already on the table is an insertion-order key. Measured on prod's 135 rows / 30 RFQs:
--
--   invited_at        NULL on 67 of 135
--   last_activity_at  fully populated, but MUTATES when a recipient acts — the label would
--                     silently reorder itself as vendors reply
--   id                gen_random_uuid(), random
--
-- BACKFILL IS REAL CHRONOLOGY, NOT A FLAT STAMP
-- ---------------------------------------------
-- Every one of the 135 existing rows has a genuine proxy, so none needs now(): 68 carry
-- invited_at, and the remaining 67 take their parent rfqs.created_at. Verified 2026-08-11 that
-- the "no proxy at all" bucket is zero. Stamping them all with the migration time would have
-- destroyed the ordering this column exists to provide.
--
-- RLS: rfq_recipients already has RLS enabled and an rfq_recipients_select policy
-- (20260301012000, replaced by 20260918000000). Adding a column changes neither; nothing here
-- touches policies or grants.

BEGIN;

ALTER TABLE public.rfq_recipients
  ADD COLUMN IF NOT EXISTS created_at timestamptz;

-- Backfill only rows that have no value yet, so re-running is a no-op.
UPDATE public.rfq_recipients rr
   SET created_at = COALESCE(rr.invited_at, r.created_at, now())
  FROM public.rfqs r
 WHERE r.id = rr.rfq_id
   AND rr.created_at IS NULL;

-- Any orphan with no matching rfqs row would be skipped by the UPDATE's join above.
UPDATE public.rfq_recipients
   SET created_at = COALESCE(invited_at, now())
 WHERE created_at IS NULL;

ALTER TABLE public.rfq_recipients
  ALTER COLUMN created_at SET DEFAULT now();

ALTER TABLE public.rfq_recipients
  ALTER COLUMN created_at SET NOT NULL;

COMMENT ON COLUMN public.rfq_recipients.created_at IS
  'Insertion time. Added by AIQ-1819: _vendor_names_for_rfq had always ordered by this column, '
  'which did not exist. Existing rows were backfilled from invited_at, else the parent RFQ''s '
  'created_at — not the migration timestamp, so the ordering is real.';

COMMIT;
