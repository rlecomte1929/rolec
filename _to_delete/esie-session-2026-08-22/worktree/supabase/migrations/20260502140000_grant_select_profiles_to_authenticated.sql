-- Hotfix: grant SELECT on public.profiles to the `authenticated` role.
--
-- Background: the admin RLS policies on feedback / error_tickets / error_logs
-- do an EXISTS subquery against public.profiles to check the caller's role.
-- That subquery runs with the caller's privileges. Without GRANT SELECT on
-- profiles, the subquery silently denies, EXISTS evaluates false, and the
-- policy rejects the read — even for legitimate admins.
--
-- profiles already has RLS enabled, so this grant does not widen visibility
-- on its own — RLS still controls which rows users can see.

grant select on public.profiles to authenticated;
