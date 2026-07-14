-- [AIQ-1528] exception_requests: reconcile prod's SQLite-shaped column types with the migration.
--
-- WHAT IS ACTUALLY WRONG (the ticket's diagnosis was off — see below).
-- Prod's public.exception_requests is typed:
--     id text, created_at text, updated_at text, resolved_at text  (+ a recommended_action column)
-- but 20260503100000_p2_exception_requests.sql declares:
--     id uuid DEFAULT gen_random_uuid(), created_at/updated_at/resolved_at timestamptz
--     (and no recommended_action at all)
--
-- The prod table is a byte-for-byte match for the SQLite dev DDL in backend/db/misc.py, not for
-- the migration. Root cause: the table was created by runtime DDL back when init_db() still ran
-- DDL on Postgres. Every run of the migration since has been a silent no-op, because
-- CREATE TABLE IF NOT EXISTS does nothing to a table that already exists — it does NOT reconcile
-- types. So the drift has been invisible: the migration "applied" cleanly and changed nothing.
--
-- WHAT IS *NOT* WRONG (do not re-fix these):
--   * init_db() does NOT run this DDL against Postgres today. It returns early twice over:
--     DISABLE_RUNTIME_DDL=1 is set on the prod service, and `if not _is_sqlite: return` sits at
--     misc.py:445, ABOVE both exception_requests blocks (misc.py:1560 and :2939). Both are
--     therefore unreachable on Postgres, and `_is_sqlite` is necessarily True where they run.
--   * Nothing is disabling RLS on redeploy. RLS is ENABLED on this table, with a policy, and anon
--     holds no grants. CREATE TABLE IF NOT EXISTS cannot disable RLS in any case.
--
-- SAFETY. 1 live row; its id already matches the uuid regex and its timestamps parse, so every
-- cast is lossless (verified against prod in a rollback transaction before this was written).
-- text -> uuid / timestamptz is a narrowing cast, so it is validated, not assumed.

BEGIN;

ALTER TABLE public.exception_requests
    ALTER COLUMN id TYPE uuid USING id::uuid,
    ALTER COLUMN id SET DEFAULT gen_random_uuid();

-- The app was supplying an id because the column had no default. With the default restored, an
-- INSERT that omits id works — which is what every caller written against the migration expects.

ALTER TABLE public.exception_requests
    ALTER COLUMN created_at TYPE timestamptz USING created_at::timestamptz,
    ALTER COLUMN created_at SET DEFAULT now();

ALTER TABLE public.exception_requests
    ALTER COLUMN updated_at TYPE timestamptz USING updated_at::timestamptz,
    ALTER COLUMN updated_at SET DEFAULT now();

-- resolved_at drifted too. The ticket missed it; it is the same bug and is fixed here rather
-- than left to rot as the next surprise.
ALTER TABLE public.exception_requests
    ALTER COLUMN resolved_at TYPE timestamptz USING resolved_at::timestamptz;

-- Re-assert the CLAUDE.md hard gate. All three are already true in prod (20260913010000 set
-- them); this is idempotent and keeps the guarantee co-located with the table it protects, so a
-- future rebuild of this table cannot quietly ship without them.
ALTER TABLE public.exception_requests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS exception_requests_service_role ON public.exception_requests;
CREATE POLICY exception_requests_service_role
  ON public.exception_requests
  FOR ALL
  TO service_role
  USING (TRUE)
  WITH CHECK (TRUE);

REVOKE ALL ON public.exception_requests FROM anon;

COMMIT;
