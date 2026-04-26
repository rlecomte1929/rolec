-- Hotfix: default feedback.user_id to auth.uid() so the client doesn't have
-- to pass it, and the WITH CHECK (auth.uid() = user_id) policy can't disagree
-- with whatever ID the client thinks it has.
--
-- Background: the frontend reads user_id from localStorage (relopass_user_id),
-- which is set from the backend authAPI response. That value is not always
-- the same as Supabase Auth's auth.users.id, so the RLS WITH CHECK rejected
-- inserts even though the user was correctly authenticated to Supabase.
-- Setting the column default to auth.uid() lets the DB fill in the right
-- value from the JWT — no client trust needed.

alter table public.feedback alter column user_id set default auth.uid();
