-- Switch the three SECURITY DEFINER views in `public` to SECURITY INVOKER so
-- they enforce RLS of the querying user, not the view creator. Resolves the
-- three "Security Definer View" errors raised by the Supabase Security
-- Advisor on `public.published_country_events`,
-- `public.published_country_resources`, and
-- `public.published_resource_sources_safe`.
--
-- Safety:
--  * Requires Postgres 15+ for `security_invoker`. Project is on Postgres
--    17.6 — supported.
--  * Each underlying table (`rkg_country_events`, `country_resources`,
--    `resource_sources`) already has RLS enabled with permissive read
--    policies for the `public` role (qual = true), so authenticated +
--    service-role callers continue to read the same rows after the switch.
--  * Each view's WHERE clause (status = 'published' AND
--    is_visible_to_end_users = true, plus the effective_from/effective_to
--    window on country_resources) is part of the view definition and runs
--    regardless of security mode — so the user-visible row set is
--    unchanged.
--  * Idempotent: ALTER VIEW … SET (...) on an already-set option is a
--    no-op.

ALTER VIEW public.published_country_events
  SET (security_invoker = on);

ALTER VIEW public.published_country_resources
  SET (security_invoker = on);

ALTER VIEW public.published_resource_sources_safe
  SET (security_invoker = on);
