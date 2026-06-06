-- F3 / AIQ-834 — make RLS a real second barrier on policy_assistant_chunks.
--
-- Today tenant isolation rests entirely on one application-layer
-- `WHERE company_id = :co` clause: RLS is enabled on the table but inert,
-- because the backend connects as the Postgres superuser (which bypasses RLS
-- unconditionally). This migration adds the structural second line of defense:
--
--   1) a dedicated least-privilege role `relopass_api` (does NOT bypass RLS), and
--   2) a request-scoped RLS policy keyed on a transaction-local GUC
--      `app.current_company_id` that the backend sets via
--      `set_config('app.current_company_id', <uuid>, true)` before each query.
--
-- With the backend connecting as `relopass_api`, a query that accidentally omits
-- the WHERE predicate STILL returns only the current company's rows — Postgres
-- enforces it.
--
-- SAFE / DARK-SHIP: the role is created NOLOGIN and nothing connects as it until
-- a human (a) sets its password out-of-band (secrets never live in a committed
-- migration) and (b) points RELOPASS_API_DATABASE_URL at it in Render. Until then
-- the backend keeps using the existing (superuser) connection and behaviour is
-- unchanged; the new policy is inert for the superuser path. See the activation
-- runbook in the PR / docs.
--
-- Scope: policy_assistant_chunks only (per task constraint). Additive — no data
-- changes, no existing policy dropped.

begin;

-- 1) Dedicated non-superuser role. Idempotent. NOLOGIN until a password is set
--    out-of-band; granting LOGIN + password is the human activation step.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'relopass_api') then
    create role relopass_api nologin;
  end if;
end$$;

-- 2) Least-privilege grants for the in-scope table. Writes are additionally
--    gated by RLS (no write policy below) so the role is effectively read-only
--    on this table until/unless a write policy is added — inserts/updates run
--    via the elevated (superuser) indexer tier, not as relopass_api.
grant usage on schema public to relopass_api;
grant select, insert, update, delete on public.policy_assistant_chunks to relopass_api;

-- Explicit CONNECT. relopass_api also inherits CONNECT via PUBLIC today, but be
-- explicit so it keeps working if PUBLIC's CONNECT is ever revoked.
grant connect on database postgres to relopass_api;

-- The retriever references `policy_assistant_chunks` and the pgvector `vector`
-- type UNQUALIFIED, so pin the role's search_path to resolve the public schema
-- (where pgvector lives) regardless of any pooler/role search_path default.
alter role relopass_api set search_path = public, extensions;

-- No sequence grants: policy_assistant_chunks.id defaults to gen_random_uuid()
-- (no SERIAL/sequence columns), so relopass_api needs no sequence privileges.

-- 3) Request-scoped second-barrier SELECT policy for relopass_api. Reads the
--    company id from a transaction-local GUC. nullif(...,'') + missing_ok=true
--    means: GUC unset/blank -> NULL -> `company_id = NULL` -> zero rows
--    (fail closed), never "all rows".
drop policy if exists pac_select_relopass_api on public.policy_assistant_chunks;
create policy pac_select_relopass_api
  on public.policy_assistant_chunks
  for select
  to relopass_api
  using (
    company_id = nullif(current_setting('app.current_company_id', true), '')::uuid
  );

comment on policy pac_select_relopass_api on public.policy_assistant_chunks is
  'F3/AIQ-834 tenant second-barrier. Backend (connected as relopass_api) sets app.current_company_id per request via set_config(...,true); RLS then blocks any other company''s rows even if the application WHERE predicate is omitted.';

commit;
