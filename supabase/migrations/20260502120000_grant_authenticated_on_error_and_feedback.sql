-- Hotfix: grant table-level privileges to the `authenticated` role on the three
-- tables added in 20260502100000 (error tracking) and 20260502110000 (feedback).
--
-- Background: when a table is created without explicit GRANT, only `postgres` and
-- `service_role` get privileges. The `authenticated` role used by the Supabase
-- JS client (after auth.signInWithPassword) gets `permission denied for table X`
-- before RLS is even consulted. Adding the grant lets the query reach RLS, which
-- already enforces the correct row-level rules.
--
-- Safety: RLS remains enabled on all three tables, so these grants do NOT widen
-- visibility — they only allow the request to reach the RLS check.

-- feedback: any authenticated user may insert their own row (RLS enforces user_id);
-- admins read/update (RLS enforces role).
grant select, insert, update on public.feedback to authenticated;

-- error_tickets: admins read + update (RLS enforces role).
grant select, update on public.error_tickets to authenticated;

-- error_logs: admins read (RLS enforces role).
grant select on public.error_logs to authenticated;
