-- Wave 1 P1 — enable the HR<->employee "compose & send" path.
--
-- public.messages was recreated thread-first in 20260520000000 with
-- thread_id / sender_id / sender_name / sender_initials NOT NULL. Migration
-- 20260529120000 added back the legacy assignment-based columns
-- (assignment_id, sender_user_id, recipient_user_id, hr_user_id, status, ...)
-- that the read path uses (db.list_messages_by_assignment / list_messages_for_hr
-- / list_messages_for_employee), but no writer was ever built, so the NOT NULLs
-- on the thread-model columns were never relaxed. The new send endpoints
-- (POST /api/hr/messages, POST /api/employee/messages) insert via the legacy
-- columns, so relax those four NOT NULLs. Their FKs already permit NULL, so this
-- changes no referential guarantees. RLS is already enabled on this table
-- (20260520000000); tenant isolation for the new writes is enforced at the
-- application layer in the handlers (HR: _hr_can_access_assignment; employee:
-- assignment ownership), exactly like the existing read endpoints which run on
-- the backend's RLS-bypassing engine.
--
-- Idempotent: ALTER COLUMN ... DROP NOT NULL is a no-op when already nullable.

ALTER TABLE public.messages ALTER COLUMN thread_id       DROP NOT NULL;
ALTER TABLE public.messages ALTER COLUMN sender_id       DROP NOT NULL;
ALTER TABLE public.messages ALTER COLUMN sender_name     DROP NOT NULL;
ALTER TABLE public.messages ALTER COLUMN sender_initials DROP NOT NULL;
