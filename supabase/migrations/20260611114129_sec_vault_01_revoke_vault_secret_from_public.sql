-- Ledger reconciliation (prod-as-oracle): applied to prod 2026-06-11 via MCP
-- apply_migration, never committed. Exact recovered SQL below. Idempotent.

-- SEC-VAULT-01: Revoke get_vault_secret() from PUBLIC role
-- Deployed: 2026-06-11
-- Before: PUBLIC (anon + authenticated) could call get_vault_secret() via PostgREST
-- After:  Only postgres + service_role retain EXECUTE

REVOKE EXECUTE ON FUNCTION public.get_vault_secret(text) FROM PUBLIC;

COMMENT ON FUNCTION public.get_vault_secret(text) IS
  'SERVICE ROLE ONLY — do not grant EXECUTE to anon, authenticated, or public. '
  'Called server-side from FastAPI backend using the service_role key only.';
