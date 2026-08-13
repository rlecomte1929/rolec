-- LEDGER RECONCILIATION — prod-as-oracle. Not new work.
--
-- This DDL was applied to production out-of-band on 2026-08-13 via MCP `apply_migration`,
-- which stamps an APPLY-TIME version rather than a repo file's. The ledger therefore carried
-- version 20260813100224 with no matching repo file, and `scripts/check_migration_drift.py`
-- failed on EVERY migration PR — not just the one that caused it — until someone reconciled it.
--
-- The statements below are recovered verbatim from
-- `supabase_migrations.schema_migrations.statements` for that version, so this file is the
-- prod state written down rather than a reconstruction. Re-running it is a no-op: every
-- statement is DROP ... IF EXISTS followed by an idempotent ADD.
--
-- See CLAUDE.md § "Ledger reconciliation (hotfix only)".
BEGIN;

-- Otto global data load: scope is now global (70+ countries) and multi-domain
-- (vehicle/domestic modules).
-- 1) Drop the hardcoded 21-country CHECK (catalog_destination_allowlist is the real
--    scope guard).
ALTER TABLE public.requirement_entities
  DROP CONSTRAINT IF EXISTS requirement_entities_destination_country_check;

-- 2) Widen the domain_area CHECK to include the module + supporting domains Otto produces.
ALTER TABLE public.requirement_entities
  DROP CONSTRAINT IF EXISTS requirement_entities_domain_area_check;

ALTER TABLE public.requirement_entities
  ADD CONSTRAINT requirement_entities_domain_area_check
  CHECK (domain_area = ANY (ARRAY[
    'immigration','registration','tax','social_security','healthcare','housing','other',
    'vehicle','vehicle_import','domestic_move','financial','employer_compliance','pet'
  ]));

COMMIT;
