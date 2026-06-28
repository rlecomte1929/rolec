-- AIQ-1366 — let the pet-import section load pets.
--
-- public.pets has RLS enabled and a correctly tenant-scoped policy
-- (`pets_via_case`: case_id IN cases the user owns / their company's HR/admin),
-- but NO table-level SELECT grant for the `authenticated` role. PostgREST checks
-- table privileges BEFORE RLS, so every frontend read (supabase.from('pets'))
-- returned 42501 permission-denied and pets could never display.
--
-- Fix: grant SELECT to `authenticated`; the existing pets_via_case policy then
-- enforces tenant scoping (employee sees own case's pets; HR/admin see their
-- company's; no cross-tenant leak). `anon` stays ungranted — pets hold PII
-- (passport, microchip, health certs). Idempotent; no policy/schema change.

GRANT SELECT ON public.pets TO authenticated;
REVOKE ALL ON public.pets FROM anon;
