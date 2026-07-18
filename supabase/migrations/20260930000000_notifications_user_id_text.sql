-- Revive the in-app notification channel for legacy text HR ids.
--
-- public.notifications.user_id was uuid, but the backend feeds it the ReloPass/HR TEXT id
-- (profiles.id / case_assignments.hr_user_id, e.g. 'seed-hr-testingapril'). So every read
-- and write for a legacy-text HR errored with 'invalid input syntax for type uuid' — the
-- bell rendered nothing and /api/notifications 500'd. The read/write path runs over the
-- superuser engine and bypasses RLS entirely (backend/db/support.py), so ONLY the column
-- type broke it — not the policies, not the callers (which already bind text). Sibling
-- tables collaboration_notifications / ops_notifications already use text.
--
-- Realtime is unaffected here (the frontend still subscribes with the Supabase auth uuid;
-- legacy HR fall back to the existing 60s poll + focus-refresh in NotificationsBell.tsx).
-- notification_preferences / notification_outbox keep their uuid user_id (their email/prefs
-- path already no-ops for legacy HR) — out of scope.
--
-- Idempotent / replay-safe: DROP POLICY IF EXISTS before recreate; ALTER ... TYPE text is a
-- no-op when already text. The two user_id indexes are rebuilt automatically by the type change.

-- The RLS policies compare user_id to auth.uid() (uuid). Drop them before the type change so
-- the expression doesn't become an invalid text = uuid comparison, then recreate with a cast.
DROP POLICY IF EXISTS "notifications_select_own" ON public.notifications;
DROP POLICY IF EXISTS "notifications_update_own_read" ON public.notifications;

ALTER TABLE public.notifications ALTER COLUMN user_id TYPE text USING user_id::text;

CREATE POLICY "notifications_select_own"
  ON public.notifications FOR SELECT TO authenticated
  USING (user_id = auth.uid()::text);

CREATE POLICY "notifications_update_own_read"
  ON public.notifications FOR UPDATE TO authenticated
  USING (user_id = auth.uid()::text)
  WITH CHECK (user_id = auth.uid()::text);
