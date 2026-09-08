-- AIQ-1523 HOTFIX — public.rfqs.created_by_user_id must not FK to auth.users.
--
-- THE BREAK
-- ---------
-- rfqs_created_by_user_id_fkey is  FOREIGN KEY (created_by_user_id) REFERENCES auth.users(id).
-- But this app authenticates on the LEGACY public.users table (the hybrid-auth model: ReloPass
-- session tokens over public.users, with Supabase auth.users only mirrored for some accounts).
-- The id the route writes is `user["id"]` — a public.users id.
--
--   public.users                     787 rows
--   ...also present in auth.users      9 rows   <-- 1.1%
--
-- So the insert violates the FK for ~99% of users. It went unnoticed because POST /api/rfqs
-- had ZERO callers: the constraint was never exercised. AIQ-1523 gave it its first caller and
-- it 500'd immediately in prod (ForeignKeyViolation on rfqs_created_by_user_id_fkey).
--
-- THE FIX
-- -------
-- Drop the FK. auth.users is the wrong boundary for a column the app fills with a legacy id,
-- and it is inconsistent with its own sibling: public.quotes.created_by_user_id is plain text
-- with no FK at all. The column stays uuid + NOT NULL — the value is a real user id, we simply
-- stop asserting it lives in a table that 99% of our users are not in.
--
-- (Same class as the feedback.user_id -> auth.users(id) FK bug: a table keyed on auth.users
-- while the app writes legacy ids.)

BEGIN;

ALTER TABLE public.rfqs
  DROP CONSTRAINT IF EXISTS rfqs_created_by_user_id_fkey;

COMMENT ON COLUMN public.rfqs.created_by_user_id IS
  'The public.users id of whoever created the RFQ (employee or HR). Deliberately NOT FK-linked to auth.users — the app authenticates on legacy public.users and only ~1% of users are mirrored into auth.users (AIQ-1523).';

COMMIT;
