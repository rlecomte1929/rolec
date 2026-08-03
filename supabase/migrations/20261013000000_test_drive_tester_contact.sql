-- TD-M0 (AIQ-1556): capture the tester's real contact at provision, so every
-- session — including dropouts who never reach the survey — is tied to a
-- reachable person. Additive columns only. test_sessions already has RLS
-- (admin-read policies from TD-1); the new columns inherit that, so the real
-- contact email is never exposed to anon. No new table → no new policy needed.
ALTER TABLE public.test_sessions ADD COLUMN IF NOT EXISTS tester_name  text;
ALTER TABLE public.test_sessions ADD COLUMN IF NOT EXISTS tester_email text;
