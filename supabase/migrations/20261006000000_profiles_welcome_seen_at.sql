-- AIQ-1701 — make the first-login welcome dismissal durable per USER, not per browser.
--
-- `/hr/welcome` and `/employee/welcome` are documented in routes.ts as "shown once per
-- user", but the only persistence was localStorage['relopass_welcome_seen_<userId>'].
-- A returning user on a new browser, a new device, or in incognito was re-onboarded.
--
-- Additive and nullable, so no backfill is needed: a NULL simply means "not yet seen",
-- which is exactly today's behaviour for every existing row. Existing table, so the
-- new-table RLS gate does not apply — `profiles` already has RLS enabled with policies,
-- and a column inherits the row's policies, so the owner can read/write this like any
-- other field on their own profile.
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS welcome_seen_at timestamptz;

COMMENT ON COLUMN public.profiles.welcome_seen_at IS
  'When the user dismissed their role first-login welcome page (AIQ-1701). NULL = not yet seen. Mirrored into localStorage at login so the redirect check stays synchronous.';
